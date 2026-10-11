"""The optional AI add-on. Off by default.

This package is the only part of LUDD that talks to a network, and only when the user has turned
AI on, chosen a provider and turned on the feature. Nothing it returns is applied by itself: the
UI shows every suggestion as a proposal to accept or dismiss, and model output that doesn't match
the expected shape is thrown away.
"""
