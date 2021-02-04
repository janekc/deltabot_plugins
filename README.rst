Deltabot Plugins
================

An extensible Delta Chat bot.

Quick Start: Running a bot+plugins in 7 steps
---------------------------------------------

0. Add Bot User
     
     $ sudo adduser <yourbotuser>
     $ tmux
     $ sudo su <yourbotuser>
     
1. Declare bot email address and password::

     $ ADDR='bot@example.com'
     $ PASSWORD='myPassword'

2. Create and activate virtual environment (Optional but recommended)::

     $ python3 -m venv ~/venvs/`echo $ADDR|tr "@" "_"`
     $ source ~/venvs/`echo $ADDR|tr "@" "_"`/bin/activate
     $ pip3 install -U pip wheel
     $ cd ~
     $ git clone https://github.com/simplebot-inc/simplebot

3. Install deltachat's python bindings as package or by compiling deltachat-core-rust::

     $ pip3 install -U -i https://m.devpi.net/dc/master deltachat==<version specified in ~/simplebot/setup.py>
     $ # or (Python 3.9.1)
     $ curl https://sh.rustup.rs -sSf | sh
     $ git clone https://github.com/deltachat/deltachat-core-rust
     $ cd deltachat-core-rust/python
     $ python install_python_bindings.py

4. Install simplebot::

     $ pip3 install ./simplebot

5. Install some plugins::

     $ cd ~
     $ git clone https://github.com/janekc/deltabot_plugins/
     $ python3 deltabot_plugins/scripts/install_plugin.py

6. Configure bot::

     $ simplebot --basedir ~/botdata/`echo $ADDR|tr "@" "_"` init $ADDR "$PASSWORD"

7. Start the bot::

     $ # sudo chown root:deltabot /var/log/mail.log
     $ simplebot --basedir ~/botdata/`echo $ADDR|tr "@" "_"` serve


Plugins
-------

SimpleBot is a bit useless without plugins, for official plugins see:

https://github.com/SimpleBot-Inc/simplebot_plugins
https://github.com/janekc/deltabot_plugins/


Installing script plugins
-------------------------

If you know how to code in Python, you can quickly create plugins and install them to tweak your bot::

    $ simplebot add-module ~/my_plugins/server_stats.py

Check the `examples` folder to see some examples about how to create plugins this way.


Note for users
--------------

SimpleBot uses `Autocrypt <https://autocrypt.org/>`_ end-to-end encryption
but note that the operator of the bot service can look into
messages that are sent to it.
