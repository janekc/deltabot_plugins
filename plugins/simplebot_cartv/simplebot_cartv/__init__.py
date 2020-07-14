# -*- coding: utf-8 -*-
from deltabot.hookspec import deltabot_hookimpl
import requests
# typing
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
# ===


version = '1.0.0'
url = 'http://eprog2.tvcdigital.cu/programacion/{}'
tv_emoji, cal_emoji, aster_emoji = '📺', '📆', '✳'
channels = {
    'Cubavisión': '5c096ea5bad1b202541503cf',
    'Tele Rebelde': '596c6d34769cf31454a473aa',
    'Educativo': '596c6d4f769cf31454a473ab',
    'Educativo 2': '596c8107670d001588a8bfc1',
    'Multivisión': '597eed8948124617b0d8b23a',
    'Clave': '5a6a056c6c40dd21604965fd',
    'Caribe': '5c5357124929db17b7429949',
    'Habana': '5c42407f4fa5d131ce00f864',
}


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name="/cartv", func=cmd_cartv)
    bot.commands.register(name="/cartv_cv", func=cmd_cv)
    bot.commands.register(name="/cartv_tr", func=cmd_tr)
    bot.commands.register(name="/cartv_ed", func=cmd_ed)
    bot.commands.register(name="/cartv_ed2", func=cmd_ed2)
    bot.commands.register(name="/cartv_mv", func=cmd_mv)
    bot.commands.register(name="/cartv_cl", func=cmd_cl)
    bot.commands.register(name="/cartv_ca", func=cmd_ca)
    bot.commands.register(name="/cartv_ha", func=cmd_ha)


def cmd_cartv(cmd: IncomingCommand) -> str:
    """Muestra la cartelera de todos los canales de la TV cubana.
    """
    text = ''
    for chan in channels.keys():
        text += get_channel(chan) + '\n\n'
    return text


def cmd_cv(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Cubavisión.
    """
    return get_channel('Cubavisión')


def cmd_tr(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Tele Rebelde.
    """
    return get_channel('Tele Rebelde')


def cmd_ed(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Educativo.
    """
    return get_channel('Educativo')


def cmd_ed2(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Educativo 2.
    """
    return get_channel('Educativo 2')


def cmd_mv(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Multivisión.
    """
    return get_channel('Multivisión')


def cmd_cl(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Clave.
    """
    return get_channel('Clave')


def cmd_ca(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Caribe.
    """
    return get_channel('Caribe')


def cmd_ha(cmd: IncomingCommand) -> str:
    """Muestra la cartelera del canal Habana.
    """
    return get_channel('Habana')


# ======== Utilities ===============

def get_channel(chan) -> str:
    with requests.get(url.format(channels[chan])) as req:
        req.raise_for_status()
        prog = req.json()

    text = '{} {}\n'.format(tv_emoji, chan)
    date = None
    for p in prog:
        if date != p['fecha_inicial']:
            date = p['fecha_inicial']
            text += '{} {}\n'.format(cal_emoji, date)
        time = p['hora_inicio'][:-3]
        title = ' '.join(p['titulo'].split())
        desc = ' '.join(p['descripcion'].split())
        trans = p['transmision'].strip()
        text += '{} {} {}\n'.format(
            aster_emoji, time, '/'.join(e for e in (title, desc, trans) if e))

    if not prog:
        text += 'Cartelera no disponible.'

    return text
