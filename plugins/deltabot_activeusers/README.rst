"Echo" Deltabot plugin
=======================

This serves as an example for how to write and package plugins
with standard Python packaging machinery.

The echo plugin registers a single `/echo` command that end-users
can send to the bot.

 $ sudo groupadd -p grouppassword deltabot
 $ sudo adduser <botuser> deltabot
 $ sudo chown root:deltabot /var/log/mail.log
