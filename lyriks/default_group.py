import typing as t

from click import Command, Context, Group
from click.utils import make_str


class DefaultGroup(Group):
    """
    A subclass of click.Group that provides a default command for the group.
    """

    def __init__(self, *args, **kwargs):
        self.default_command = kwargs.pop('default_command', None)
        super().__init__(*args, **kwargs)

    def resolve_command(
            self, ctx: Context, args: t.List[str]
    ) -> t.Tuple[t.Optional[str], t.Optional[Command], t.List[str]]:
        cmd_name = make_str(args[0])

        cmd = self.get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd_name, cmd, args[1:]

        return None, self.get_default_command(), args

    def get_default_command(self) -> Command:
        if self.default_command is None:
            raise AttributeError('No default command set')
        return self.commands.get(self.default_command)

    def get_help(self, ctx: Context) -> str:
        return self.get_default_command().get_help(ctx)
