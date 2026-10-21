M4 vision / prompt-grid evidence for Niko1221/Strata PR #2903
===========================================================

This branch is an evidence archive, not a competing pull request and not a new
engine release. No model weights, real user screenshots, credentials, machine
paths or private conversations are included. The 12 cards are synthetic fixtures.

Provenance and limits
---------------------
Hardware: Apple M4 Max, 128 GB unified memory; macOS 27.0.1 (26A434).
Engine: 0.1.46, built from a7bdbfdabc9a3e7c83e3dbc2441d0933569d773e
with the exact local-combined-fix.patch retained here.
Patch SHA-256:
  c1ea450a1391a4241c935ab424f7b71b0c4232b777b80362380b10780ec9b541
Previously tested local executable SHA-256:
  5c558fea9344e09f808a9558cbb393d90e522a85bbdcb9fd41fab247750170b6
Dependencies: Apple metal-cpp 26; llama.cpp/ggml
  3cf03257f219afbe7334045ff7c6a06ac68c627d.

These are previously recorded local measurements, not a new run of this archive
branch and NOT execution of PR #2903 head fa8a30927645f486876c6e8c9f73b07797bda44b.
The local patch uses per-layer Metal function constants rather than that PR's
expanded plan arguments. It also contains a separate workspace ownership repair,
now submitted independently as https://github.com/Niko1221/Strata/pull/3527.
The full deployment retained its existing server/client customizations. Its
end-to-end observations are not a clean-upstream integration proof or evidence
that the grid change alone caused every reported outcome.

Controlled numerical evidence
-----------------------------
With the actual M4 Q4_K gate/up tile (16 output columns), NFF=640 needs 40 groups.
The former engine grid launches 10, so 480 of 640 columns are not written.
The local parity harness uses real indirect dispatch, not a substitute tile.

From the saved logs (Q4_K/Q5_1, T=32, 64 experts):
  legacy grid: relative L2 to fp16-operand reference 8.30e-01, FAIL
  fixed grid:  relative L2 to fp16-operand reference 2.40e-05, PASS
The exact-float reference error after fixing the grid was 4.14e-04.
Additional logs cover Q5_K, Q6_K, Q8_0, IQ4_XS, Q2_0 and mixed per-layer grids.

The following are reproduction commands for the retained harness. The reported
outputs are historical logs, not a claim these commands were rerun while uploading:

  git checkout a7bdbfdabc9a3e7c83e3dbc2441d0933569d773e
  git apply /path/to/local-combined-fix.patch
  cmake -S metal -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DMETAL_CPP_DIR=<metal-cpp-26> -DSTRATA_GGML_DIR=<llama.cpp-3cf03257> \
    -DGGML_CCACHE=OFF
  cmake --build build --target moe_mm_parity prompt_grid_parity -j 6
  build/moe_mm_parity --legacy-engine-grid --gu Q4_K --dn Q5_1 --T 32
  build/moe_mm_parity --engine-grid --gu Q4_K --dn Q5_1 --T 32
  build/prompt_grid_parity

Multi-image deployment observations
-----------------------------------
The synthetic-card subset is in multi-image-cases-and-results.json: 20 case/result
pairs, all graded as matching the expected parsed values. It covers 3/4/6/8/12
images, reversal, repeated/shuffled images, seven-image history, tools and schema.
Some answers used Markdown fences despite the formatting instruction; "passed"
here means the parsed expected values matched, not perfect raw JSON compliance.
The larger historical combined suite was 29/29; this archive includes only the
synthetic-card subset rather than unrelated photos/UI fixtures and speed probes.

Model: Unsloth Qwen3.8-Flash-Next UD-Q4_K_XL, unchanged F16 vision projector,
official engine 0.1.46 GPU vision helper; max image tokens 1024.
Context 131072; KV int8; resident Metal path; MTP off for this suite.
Environment: STRATA_METAL_STREAM=0, STRATA_HC_Q8=0, STRATA_ROUTE_TAIL_SKIP=0,
  STRATA_METAL_PROMPT_CHUNK=1024.
Requests: temperature=0, top_k=1, top_p=1, seed=42, presence_penalty=0,
  repetition_penalty=1, enable_thinking=false, reasoning_effort=none,
  max_tokens=512; streaming OpenAI-compatible chat completions.
Use each case's system/prompt and its ordered fixture list. For history cases,
carry the referenced conversation's previous messages and actual responses.
Position 'after' places the question after images; 'interleaved' places an image
label before each image; ids=true also requests add_vision_id in the chat template.
Tools/response_format fields are preserved in the corresponding case records.

Not established: correctness on every image/model/chip, full 128K-context stress,
exact PR #2903 hardware validation, a general throughput gain, or that the source
patch alone recreates all settings/customizations of the original deployment.
No inference was started and no installed model/config was modified for this upload.
