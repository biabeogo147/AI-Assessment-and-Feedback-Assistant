"""LangGraph graphs, one per authoring task.

A graph rather than a function call because two of these tasks have a shape a
straight line cannot hold: writing a question can fail its own check and need
another go. Keeping the third one -- the tutoring turn -- in the same form
costs a few lines and means a reader learns one pattern, not two.

Nothing in here knows about Redis, arq or the queue. A graph composes a prompt,
calls a model, and hands back what came out; publishing it is the handler's
job, because the handler is the part that was given a connection.
"""
