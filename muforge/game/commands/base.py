from muforge.shared.commands import Command as BaseCommand

class Command(BaseCommand):

    def __init__(self, match_cmd, match_data: dict[str, str], enactor):
        super().__init__(match_cmd, match_data)
        self.enactor = enactor