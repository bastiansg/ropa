from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

MAX_HISTORY_MESSAGES = 20


def trim_history(
    messages: list[ModelMessage],
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[ModelMessage]:
    cutoff = max(0, len(messages) - limit)
    start = next(
        (
            index
            for index in range(cutoff, len(messages))
            if isinstance(messages[index], ModelRequest)
            and any(
                isinstance(part, UserPromptPart)
                for part in messages[index].parts
            )
        ),
        len(messages),
    )

    return messages[start:]
