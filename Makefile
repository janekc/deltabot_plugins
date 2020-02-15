.PHONY: all
all: echo friends groupmaster help tictactoe translator webgrabber wikiquote xkcd admin shortcuts rss facebook mastodon avatar meme cuba_weather cartv xmpp chess

.PHONY: echo
echo:
	echo y | pip uninstall simplebot_echo; pip install simplebot_echo

.PHONY: cartv
cartv:
	echo y | pip uninstall simplebot_cartv; pip install simplebot_cartv

.PHONY: cuba_weather
cuba_weather:
	echo y | pip uninstall simplebot_cubaweather; pip install simplebot_cubaweather

.PHONY: friends
friends:
	echo y | pip uninstall simplebot_friends; pip install simplebot_friends

.PHONY: groupmaster
groupmaster:
	echo y | pip uninstall simplebot_groupmaster; pip install simplebot_groupmaster

.PHONY: help
help:
	echo y | pip uninstall simplebot_help; pip install simplebot_help

.PHONY: tictactoe
tictactoe:
	echo y | pip uninstall simplebot_tictactoe; pip install simplebot_tictactoe

.PHONY: translator
translator:
	echo y | pip uninstall simplebot_translator; pip install simplebot_translator

.PHONY: webgrabber
webgrabber:
	echo y | pip uninstall simplebot_webgrabber; pip install simplebot_webgrabber

.PHONY: wikiquote
wikiquote:
	echo y | pip uninstall simplebot_wikiquote; pip install simplebot_wikiquote

.PHONY: xkcd
xkcd:
	echo y | pip uninstall simplebot_xkcd; pip install simplebot_xkcd

.PHONY: admin
admin:
	echo y | pip uninstall simplebot_admin; pip install simplebot_admin

.PHONY: shortcuts
shortcuts:
	echo y | pip uninstall simplebot_shortcuts; pip install simplebot_shortcuts

.PHONY: rss
rss:
	echo y | pip uninstall simplebot_rss; pip install simplebot_rss

.PHONY: facebook
facebook:
	echo y | pip uninstall simplebot_facebook; pip install simplebot_facebook

.PHONY: mastodon
mastodon:
	echo y | pip uninstall simplebot_mastodon; pip install simplebot_mastodon

.PHONY: avatar
avatar:
	echo y | pip uninstall simplebot_avatar; pip install simplebot_avatar

.PHONY: meme
meme:
	echo y | pip uninstall simplebot_meme; pip install simplebot_meme

.PHONY: xmpp
xmpp:
	echo y | pip uninstall simplebot_xmpp; pip install simplebot_xmpp

.PHONY: chess
chess:
	echo y | pip uninstall simplebot_chess; pip install simplebot_chess
