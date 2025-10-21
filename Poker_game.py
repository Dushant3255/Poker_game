# Poker_game.py  (fixed)
from Poker_core import TexasHoldemGame, cards_str, describe_eval

# --- Default human prompt (used if no custom action_fn is given) ---
def get_action(player, current_bet):
    while True:
        print("\n")
        print(f"\n{player.name}'s turn (stack={player.stack}, bet={player.bet}, current bet={current_bet})")
        if player.stack <= 0:
            print("You are all-in!")
            return "call", 0
        action = input("Choose action [fold/call/check/raise/allin]: ").strip().lower()
        if action in ["fold", "call", "check", "raise", "allin"]:
            if action == "raise":
                try:
                    amt = int(input("Enter raise amount: "))
                    if amt <= 0 or amt > player.stack:
                        print("Invalid amount.")
                        continue
                    return action, amt
                except ValueError:
                    print("Invalid input.")
                    continue
            return action, 0
        else:
            print("Invalid choice. Try again.")

# --- Betting loop with correct termination & pluggable action source ---
def betting_round(game, current_bet=0, action_fn=None):
    """
    Runs a betting round until:
      - only one player remains in_hand, or
      - no one wants to raise and all players have acted since the last raise.

    Parameters
    ----------
    game : TexasHoldemGame
    current_bet : int
        The current highest bet to match at the start of this round.
        For preflop, pass game.big_blind; for postflop streets, pass 0.
    action_fn : callable or None
        A function (player, current_bet) -> (action:str, amount:int).
        If None, uses interactive get_action() for all players.
    """
    if action_fn is None:
        action_fn = get_action

    # Ensure everyone has in_hand set
    for p in game.players:
        if not hasattr(p, "in_hand"):
            p.in_hand = True

    def active_players():
        return [p for p in game.players if p.in_hand and p.stack >= 0]

    players = active_players()
    if len(players) <= 1:
        return current_bet

    # The number of players who still need to act since the last raise.
    to_go = len(players)
    idx = 0

    while True:
        # If only one player remains, round ends.
        players = active_players()
        if len(players) <= 1:
            break

        player = players[idx % len(players)]
        to_call = max(0, current_bet - player.bet)

        # If player is all-in, they are treated as having acted; skip.
        if not player.in_hand or player.stack == 0:
            idx += 1
            # If we've cycled through everyone with no pending actions, end.
            if to_go <= 0:
                break
            continue

        # Ask for action
        act, amt = action_fn(player, current_bet)

        if act == "fold":
            player.in_hand = False
            # A fold counts as having acted; reduce to_go and possibly end if only one left.
            to_go -= 1

        elif act == "check":
            # Only valid if nothing to call
            if to_call > 0:
                # invalid -> treat as call
                pay = min(to_call, player.stack)
                player.stack -= pay
                player.bet += pay
                game.pot += pay
            # counts as an action without changing current_bet
            to_go -= 1

        elif act == "call":
            pay = min(to_call, player.stack)
            player.stack -= pay
            player.bet += pay
            game.pot += pay
            to_go -= 1

        elif act == "raise":
            # total they put in this turn = to_call + amt
            total = to_call + min(amt, player.stack)
            player.stack -= total
            player.bet += total
            game.pot += total
            # New bet to match
            if player.bet > current_bet:
                current_bet = player.bet
            # After a raise, everyone else must act again
            to_go = len(active_players()) - 1

        elif act == "allin":
            # Push entire stack
            total = player.stack
            player.stack = 0
            player.bet += total
            game.pot += total
            if player.bet > current_bet:
                current_bet = player.bet
                to_go = len(active_players()) - 1
            else:
                to_go -= 1

        # Move to next active player
        idx += 1

        # Round is done when all active players have acted since last raise
        if to_go <= 0:
            break

    return current_bet

# --- Optional fully-interactive demo (unchanged, now using fixed engine) ---
def play_hand_with_actions():
    print("\n--- Texas Hold'em Interactive Game ---\n")
    names = input("Enter player names (comma-separated): ").split(",")
    names = [n.strip() for n in names if n.strip()]
    game = TexasHoldemGame(names, blinds=(10, 20))
    game.post_blinds()
    game.deal_hole()

    print("\n--- Hole Cards ---")
    for p in game.players:
        print(f"{p.name}: {cards_str(p.hole)}")

    # Preflop
    print("\n--- Preflop ---")
    current_bet = game.big_blind
    betting_round(game, current_bet)

    # Flop
    game.deal_flop()
    print("Flop:", cards_str(game.board))
    betting_round(game, 0)

    # Turn
    game.deal_turn()
    print("Turn:", cards_str(game.board))
    betting_round(game, 0)

    # River
    game.deal_river()
    print("River:", cards_str(game.board))
    betting_round(game, 0)

    # Showdown
    winners, detail = game.showdown()
    print("\n--- Showdown ---")
    for i, p in enumerate(game.players):
        if p.in_hand:
            print(f"{p.name:8} -> {describe_eval(detail[i])}")
    if len(winners) == 1:
        print(f"\nWinner: {game.players[winners[0]].name} wins the pot of {game.pot}")
    else:
        names = ", ".join(game.players[i].name for i in winners)
        print(f"\nSplit pot between: {names} (pot={game.pot})")

if __name__ == "__main__":
    play_hand_with_actions()
