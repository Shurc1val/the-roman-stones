"""Module to contain and run the endpoints for the Deloton staff API"""

from random import randint

from flask import Flask, render_template, request, Response, redirect, url_for, make_response
from flask_login import LoginManager, login_user, current_user, AnonymousUserMixin
from turbo_flask import Turbo

import backend
from time import sleep


class User():

    def __init__(self, users: list) -> None:
        user_ids = [int(user.get_id()) for user in users]
        self._user_id = self.get_new_user_id(user_ids)

    def get_id(self):
        return self._user_id
    
    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False
    
    @property
    def four(self):
        return 4
    
    @staticmethod
    def get_new_user_id(user_ids: list[int]) -> int:
        """Gets a unique user id."""
        user_id = randint(1, 100000)
        while user_id in user_ids:
            user_id = randint(1, 100000)
        
        return str(user_id)



app = Flask(__name__, template_folder='templates')
app.json.sort_keys = False
app.secret_key = "Actually at Aikmains"

login_manager = LoginManager()
login_manager.init_app(app)
users = []

turbo = Turbo(app)

COLOURS_AVAILABLE = ['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet']


@turbo.user_id
def get_user_id():
    return current_user.get_id()


@login_manager.user_loader
def load_user(user_id: str) -> User:
    matches = [user for user in users if user.get_id() == user_id]
    if len(matches) == 0:
        return None
    
    return matches[0]


def login_redirect(func):
  """Decorator to make all game interactions first require a login."""
  def redirected_func(*args, **kwargs):
    user_id = current_user.get_id()
    if user_id in [user.get_id() for user in users]:
        return func(*args, **kwargs)
    else:
        return redirect(url_for('login'), code=302)

  redirected_func.__name__ = func.__name__

  return redirected_func


@app.route("/login", methods=["GET", "POST"])
def login():
    """Function to make new players login."""
    if request.method == "GET":
        player_colours = [player.colour for player in game.players]
        #player_colours = ['red']
        available_colours_remaining = list(set(COLOURS_AVAILABLE).difference(set(player_colours)))

        user_id = current_user.get_id()
        
        if not user_id:
            user = User(users)
            if login_user(user):
                users.append(user)
        elif user_id in game.player_ids:
            return redirect(url_for('display_game'))

        if len(game.players) < game.number_of_players:
            message = {'players': player_colours, 'colours_available': available_colours_remaining}
        else:
            message = {'title': "Game Full", 'text': "Sorry, there are no spots left in this game; feel free to watch."}
            return render_template('TRS.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message=message)

        return render_template('TRS.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = None, player_turn = "", message=message)

    elif request.method == "POST":
        user_id = current_user.get_id()

        num_players = request.form.get('num_players')
        counters_per_player = request.form.get('counters_per_player')
        colour = request.form.get('colour').lower()
        
        if num_players and counters_per_player:
            game.counters_per_player = int(counters_per_player)
            game.number_of_players = int(num_players)
        
        game.add_player(backend.Player(colour, user_id))

        if len(game.players) < game.number_of_players:
            non_player_ids = list(set([user.get_id() for user in users]).difference(set(game.player_ids)))
            player_colours = [player.colour for player in game.players]
            available_colours_remaining = list(set(COLOURS_AVAILABLE).difference(set(player_colours)))
            print(COLOURS_AVAILABLE, player_colours)
            print([user.get_id() for user in users])
            turbo.push(turbo.replace(render_template('game.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = None, player_turn = "", message={'players': player_colours, 'colours_available': available_colours_remaining}), 'game'), to=non_player_ids)
            turbo.push(turbo.replace(render_template('game.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = None, player_turn = "", message={'title': "Please Wait", 'text': f"Please wait for the rest of the players to join ({len(game.players)}/{game.number_of_players})."}), 'game'), to=game.player_ids)
        else:
            turbo.push(turbo.replace(render_template('game.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message={}), 'game'))
            return {}, 200
        
        return redirect(url_for('display_game'))


@app.route("/", methods=["GET"])
@login_redirect
def display_game():
    """ Creates an index route with an index page for the API """
    message = {}
    user_id = current_user.get_id()
    if len(game.players) < game.number_of_players:
        if user_id not in game.player_ids:
            return redirect(url_for('login'))
        else:
            message = {'title': "Please Wait", 'text': f"Please wait for the rest of the players to join ({len(game.players)}/{game.number_of_players})."}

    return render_template('TRS.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message=message)


@app.route("/move_piece", methods = ["POST"])
@login_redirect
def move_piece():
    colour = game.players[0].colour
    game.move_piece(int(request.form['square_num']), request.form['colour'], current_user.get_id())
    turbo.push([
        turbo.replace(render_template('board.html', counters=game.board), 'board'),
        turbo.replace(render_template('player_turn_label.html', player_turn = game.players[0].colour), 'player_turn_label'),
        turbo.replace(render_template('off_board.html', finished_tokens=game.finished_tokens), 'off_board')        
        ])
    if game.check_win(colour):
        turbo.push(turbo.replace(render_template('game.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message={'title': "Winner", 'text': f"Congratulations {colour} player, you have won!"}), 'game'))
    return Response(status=200)


@app.route("/roll_die", methods=["POST"])
@login_redirect
def roll_die():
    """Function to roll a die, if it's not already been rolled."""
    if not game._validate_user(current_user.get_id()):
        redirect(url_for('display_game'))
        return Response(status=400)

    time_s = randint(1,3) / 100
    time_threshold = randint(3, 5) / 10
    if game.players[0].die_roll == 0:
        with app.app_context():
            while time_s < time_threshold:
                sleep(time_s)
                turbo.push(turbo.replace(render_template('die_image.html', die_number=randint(1,6)), 'die_image'))
                time_s *= 1.2
            
            game.players[0].reset_die()
            game.players[0].roll_die()
            turbo.push(turbo.replace(render_template('die_image.html', die_number=game.players[0].die_roll), 'die_image'))

    if not game.check_if_moves_exist():
        game.players[0].reset_die()
        message = {
            'title': "No Moves Available",
            'text': f"Sorry {game.players[0].colour}, you have no moves available!"
        }
        turbo.push(turbo.replace(render_template('board.html', counters=game.board, message=message), "board"), to=current_user.get_id())
        game.next_player()
    
    return Response(status=200)


@app.route("/close_popup", methods=["POST"])
@login_redirect
def close_popup():
    """Function to close popup when okay button pressed."""
    turbo.push(turbo.replace(render_template('popup.html', message={}), 'popup_box'), to=current_user.get_id())
    turbo.push(turbo.replace(render_template('controls.html', finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message={}), 'controls'))
    return redirect(url_for('display_game'))


@app.route("/quit_game", methods=["GET", "POST"])
def quit_game():
    """Allows a player to leave the game."""
    if request.method == "GET":
        user_id = current_user.get_id()
        turbo.push(turbo.replace(render_template('popup.html', message={'title': "Quit Game", 'text': "This will remove you and all your counters from the board. Are you sure you want to leave?"}), "popup_box"), to=user_id)
        return Response(status=200)
    elif request.method == "POST":
        user_id = current_user.get_id() 
        game.remove_player(user_id)
        turbo.push(turbo.replace(render_template('game.html', counters = game.board, finished_tokens = game.finished_tokens, die_number = game.players[0].die_roll, player_turn = game.players[0].colour, message={}), "game"))
        return redirect(url_for('login'))



if __name__ == "app":
    game = backend.Game()
