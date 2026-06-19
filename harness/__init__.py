"""Keystone Engineering Harness: deterministic governance pipeline for agent-authored code.

Coding agents can write patches. Keystone decides if they are safe to merge.

The harness wraps every agent-proposed change through the Orbit code graph,
computes blast radius, evaluates the policy gate, detects cross-MR collisions,
and produces a structured verdict. No model decides; the engine decides.
"""
