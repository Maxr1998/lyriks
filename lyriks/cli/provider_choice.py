from click import Choice

from lyriks.providers.registry import provider_registry


class ProviderChoice(Choice):
    """
    A click Choice type to pick a provider from the registry.
    """

    def __init__(self):
        super().__init__(provider_registry.keys(), case_sensitive=False)

    def convert(self, value, param, ctx):
        # Validate and normalize allowed choice strings
        value = super().convert(value, param, ctx)

        provider_class = provider_registry.get(value)
        if provider_class is None:
            self.fail(
                self.get_invalid_choice_message(value=value, ctx=ctx),
                param=param,
                ctx=ctx,
            )

        return provider_class
