from enum import Enum


class OpportunityStructure(str, Enum):
    TREND_INITIATION_PULLBACK = "trend_initiation_pullback"
    CONTINUATION_AFTER_CONSOLIDATION = "continuation_after_consolidation"
    FAILED_BREAKOUT_REVERSAL = "failed_breakout_reversal"
    VOLATILITY_EXPANSION_AFTER_COMPRESSION = "volatility_expansion_after_compression"
    EXPECTATION_SHIFT_SECOND_LEG = "expectation_shift_second_leg"


class EdgeSource(str, Enum):
    TREND_CONTINUATION = "trend_continuation"
    VOLATILITY_EXPANSION = "volatility_expansion"
    POSITIONING_SQUEEZE = "positioning_squeeze"
    EXPECTATION_SHIFT = "expectation_shift"
    LIQUIDITY_DISLOCATION = "liquidity_dislocation"
    BEHAVIOR_FLOW_ASYMMETRY = "behavior_flow_asymmetry"


class FailureType(str, Enum):
    DIRECTION_WRONG = "direction_wrong"
    TIMING_WRONG = "timing_wrong"
    SIZING_WRONG = "sizing_wrong"
    EXECUTION_WRONG = "execution_wrong"
    MANAGEMENT_WRONG = "management_wrong"
    REGIME_MISMATCH = "regime_mismatch"
    SHOULD_NOT_HAVE_TRADED = "should_not_have_traded"


class ReviewConclusion(str, Enum):
    VALID_PATTERN_VALID_TRADE = "valid_pattern_valid_trade"
    VALID_PATTERN_INVALID_TRADE = "valid_pattern_invalid_trade"
    INVALID_PATTERN_BUT_PROFIT = "invalid_pattern_but_profit"
    INVALID_PATTERN_INVALID_TRADE = "invalid_pattern_invalid_trade"
    NEED_MORE_EVIDENCE = "need_more_evidence"


def trade_review_taxonomy() -> dict[str, list[str]]:
    return {
        "opportunity_structure": [item.value for item in OpportunityStructure],
        "edge_source": [item.value for item in EdgeSource],
        "failure_type": [item.value for item in FailureType],
        "review_conclusion": [item.value for item in ReviewConclusion],
    }
