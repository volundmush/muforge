    async def system_pinger(self):
        from muforge.shared.events.system import SystemPing

        try:
            while True:
                for k, v in muforge.SESSIONS.items():
                    await v.send_event(SystemPing())
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            return
