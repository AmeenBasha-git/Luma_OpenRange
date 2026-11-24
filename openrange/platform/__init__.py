"""Platform layer: where the sponsor tools plug in.

    bus.py     agent-to-agent messages   (LocalBus now, BAND later)
    skills.py  catalogue of every module (exported for Finch)

Lyzr (orchestration) wraps orchestrator/, AdaL and Agent37 host each agent.
The trading logic never depends on these tools directly, so any of them can be swapped.
"""
