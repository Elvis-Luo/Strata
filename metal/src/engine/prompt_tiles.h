#pragma once
#include "ref_quant.h"
#include <cstdint>
#include <string>

namespace strata_metal {
struct PromptTile {
    int rows, columns, reduction, simdgroups;
    std::string suffix() const {
        return "_" + std::to_string(rows) + "_" + std::to_string(columns) + "_" +
               std::to_string(reduction) + "_" + std::to_string(simdgroups);
    }
    uint32_t grid_columns(int outputs) const {
        return (outputs + columns - 1) / columns;
    }
};

// Keep the selected kernel and its indirect grid derived from the same tile.
inline PromptTile prompt_gu_v2_tile(int type) {
    if (type == ref::Q4_K || type == ref::Q5_K || type == ref::Q6_K) return {16, 16, 128, 2};
    if (type == ref::Q8_0 || type == ref::IQ4_XS) return {16, 64, 32, 2};
    return {16, 64, 16, 2};
}
inline PromptTile prompt_down_v2_tile(int type) {
    return {16, 64, type == ref::IQ4_NL || type == ref::Q5_1 || type == ref::Q8_0 ? 32 : 16, 2};
}
}  // namespace strata_metal
