# -*- coding: utf-8 -*-
from simplebot import Plugin, PluginCommand
from cuba_weather import RCApiClient


class CubaWeather(Plugin):

    name = 'CubaWeather'
    version = '0.1.0'
    description = 'Buscar información del clima usando redcuba.cu'

    @classmethod
    def activate(cls, bot):
        super().activate(bot)

        cls.commands = [
            PluginCommand('/cuwtr', ['<lugar>'], 'Buscar información del clima para el lugar dado', cls.cuwtr_cmd)]
        cls.bot.add_commands(cls.commands)

    @classmethod
    def cuwtr_cmd(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)

        if ctx.text:
            api = RCApiClient()
            weather = api.get(ctx.text, suggestion=True)
            chat.send_text(str(weather))
        else:
            chat.send_text('Enviame un lugar de Cuba, ej: /cuwtr Santiago')
