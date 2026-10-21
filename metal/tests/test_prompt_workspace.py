#!/usr/bin/env python3
"""Exercise the production pc_setup allocation code on Metal without a model.

Window otherwise requires an initialized model/session. Extract its buffer struct,
geometry constants and complete pc_setup method into a small allocation-only shim.
No allocation/free statements are reimplemented by the test. Link the real mtl_rt and
use weak Objective-C references to check every old MTLBuffer is deallocated.
This is a resource-lifetime test, not a model or prompt-kernel correctness test.

CTest supplies --runtime. --source-ref <base> can test the unpatched source with the
same harness/library; it should fail when the first workspace grows.
"""

import argparse
import pathlib
import re
import subprocess
import tempfile


def section(text, first, last):
    start = text.index(first)
    return text[start:text.index(last, start)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", required=True)
    parser.add_argument("--runtime", type=pathlib.Path, required=True)
    parser.add_argument("--build-dir", type=pathlib.Path, required=True)
    parser.add_argument("--source-ref", help="git revision for the negative control")
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]

    def read(path):
        if args.source_ref:
            return subprocess.check_output(
                ["git", "show", f"{args.source_ref}:{path}"], cwd=root, text=True
            )
        return (root / path).read_text(encoding="utf-8")

    window = read("metal/src/engine/window.cpp")
    chain = read("metal/src/engine/prompt_chain.inc")
    buffers = section(window, "struct PromptBufs {", "// The vision path")
    geometry = section(window, "constexpr int N =", "constexpr int P_MAXE")
    constants = section(chain, "constexpr int PC_QB", "struct PcDqArgs")
    setup = section(chain, "bool Window::pc_setup(int C)", "// one chunk of nT rows")

    # Enumerate the actual Buffer members, including arrays. This also checks
    # newly added buffers without depending on the fix's ownership vector.
    declaration = re.search(r"mtl::Buffer\s+([^;]+);", buffers)
    if declaration is None:
        raise RuntimeError("PromptBufs no longer has the expected buffer declaration")
    names = []
    for field in declaration.group(1).split(","):
        match = re.fullmatch(r"\s*(\w+)(?:\[(\d+)\])?\s*", field)
        if match is None:
            raise RuntimeError(f"unrecognized buffer member: {field!r}")
        name, count = match.groups()
        if count:
            names.extend(f"{name}[{i}]" for i in range(int(count)))
        else:
            names.append(name)
    references = ", ".join("&w.pb_." + name for name in names)

    harness = r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "mtl_rt.h"
#include <array>
#include <chrono>
#include <cstdio>
#include <set>
#include <vector>

@GEOMETRY@
@CONSTANTS@
@BUFFERS@
double now_ms() {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct Window {
    mtl::Context* cx_;
    PromptBufs pb_;
    int64_t max_cells_ = 131200;
    // The allocation lifetime does not depend on the M4/M5 kernel layout probe.
    bool coop_k4() { return false; }
    bool pc_setup(int C);
};
@SETUP@

bool setup(Window& w, int capacity) {
    // Drain framework temporaries before observing the retained buffer handles.
    @autoreleasepool { return w.pc_setup(capacity); }
}

bool require(bool ok, const char* what) {
    std::printf("%s: %s\n", ok ? "PASS" : "FAIL", what);
    return ok;
}

int main() {
    @autoreleasepool {
        if (MTLCreateSystemDefaultDevice() == nil) {
            std::puts("SKIP: no Metal device available");
            return 77;
        }
        mtl::Context cx;
        std::printf("device: %s; %d prompt buffers; no model loaded\n",
                    cx.device_name().c_str(), @COUNT@);
        Window w{&cx};
        std::array<mtl::Buffer*, @COUNT@> buffers{@REFERENCES@};
        if (!setup(w, 64)) return 1;
        const std::array<int, 3> libraries{w.pb_.lib, w.pb_.lgdn, w.pb_.lqsa};
        for (int capacity : {96, 128, 192}) {
            NSPointerArray* previous;
            const int old_capacity = w.pb_.C;
            @autoreleasepool {
                previous = [NSPointerArray weakObjectsPointerArray];
                std::set<void*> handles;
                bool distinct = true;
                for (const auto* b : buffers) {
                    distinct = distinct && b->handle && handles.insert(b->handle).second;
                    [previous addPointer:b->handle];
                }
                if (!require(distinct, "every workspace member has a distinct live buffer")) return 1;
                w.pb_.R.as<float>()[0] = 123.0f;
                const uint64_t allocations = cx.allocated();
                if (!setup(w, old_capacity) || !setup(w, old_capacity / 2)) return 1;
                bool same = cx.allocated() == allocations && w.pb_.C == old_capacity &&
                            w.pb_.R.as<float>()[0] == 123.0f;
                // Reading a weak slot can temporarily retain/autorelease its referent.
                // End those observation references before testing deallocation.
                for (size_t i = 0; i < buffers.size(); ++i)
                    same = same && [previous pointerAtIndex:i] == buffers[i]->handle;
                if (!require(same, "same/smaller request reuses every buffer and its contents")) return 1;
            }  // Drain references made while growing/reading the weak pointer array.

            if (!setup(w, capacity)) return 1;
            size_t retained = 0;
            for (NSUInteger i = 0; i < previous.count; ++i)
                retained += [previous pointerAtIndex:i] != nullptr;
            std::printf("capacity %d -> %d: old buffers retained = %zu of %zu\n",
                        old_capacity, capacity, retained, buffers.size());
            if (!require(retained == 0, "growth releases all old Metal buffers")) return 1;
            if (!require(w.pb_.C == capacity && libraries ==
                         std::array<int, 3>{w.pb_.lib, w.pb_.lgdn, w.pb_.lqsa},
                         "growth keeps the compiled libraries and new capacity")) return 1;
            bool usable = true;
            for (auto* b : buffers) usable = usable && b->handle && b->ptr && b->bytes;
            if (!require(usable, "all replacement buffers are usable")) return 1;
            for (auto* b : buffers) b->as<uint32_t>()[0] = 17;
        }
        // Only scratch allocation is exercised; no model, KV state or forward pass.
        for (auto* b : buffers) cx.free(*b);
        std::puts("prompt workspace lifetime: PASS");
    }
}
'''
    for marker, value in {
        "@GEOMETRY@": geometry, "@CONSTANTS@": constants,
        "@BUFFERS@": buffers, "@SETUP@": setup,
        "@COUNT@": str(len(names)), "@REFERENCES@": references,
    }.items():
        harness = harness.replace(marker, value)
    args.build_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lifetime-", dir=args.build_dir) as tmp:
        source = pathlib.Path(tmp) / "prompt_workspace.mm"
        binary = pathlib.Path(tmp) / "prompt_workspace"
        source.write_text(harness, encoding="utf-8")
        subprocess.run([
            args.cxx, "-std=c++20", "-O1", "-fobjc-arc",
            "-I", str(root / "metal/src"), str(source), str(args.runtime.resolve()),
            "-framework", "Metal", "-framework", "Foundation", "-o", str(binary),
        ], check=True)
        return subprocess.run([str(binary)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
