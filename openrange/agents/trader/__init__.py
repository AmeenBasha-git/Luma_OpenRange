"""Trader Agent: T1 Signal -> T2 Gate -> T3 Risk -> T4 Broker -> T5 Monitor -> T6 Journal.

T1-T5 are pure code: they must never import the LLM client (tests/test_no_llm_in_order_path.py).
"""
