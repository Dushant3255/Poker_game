from Poker_core import TexasHoldemGame, cards_str, describe_eval
import math

# --- Helper Functions ---
def get_action(player, current_bet):
    while True:
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


def betting_round(game, current_bet=0):
    """Simplified betting loop."""
    players = [p for p in game.players if p.in_hand and p.stack > 0]
    if len(players) <= 1:
        return current_bet

    last_raiser = None
    active_players = len(players)
    idx = 0
    while True:
        player = players[idx % len(players)]
        if not player.in_hand:
            idx += 1
            continue

        action, amt = get_action(player, current_bet)
        if action == "fold":
            player.in_hand = False
            print(f"{player.name} folds.")
            active_players -= 1
            if active_players == 1:
                break
        elif action == "check":
            if player.bet < current_bet:
                print("You cannot check; must call or fold.")
                continue
            print(f"{player.name} checks.")
        elif action == "call":
            to_call = current_bet - player.bet
            bet = min(to_call, player.stack)
            player.stack -= bet
            player.bet += bet
            game.pot += bet
            print(f"{player.name} calls {bet}.")
        elif action == "raise":
            to_call = current_bet - player.bet
            total = to_call + amt
            player.stack -= total
            player.bet += total
            game.pot += total
            current_bet = player.bet
            last_raiser = player
            print(f"{player.name} raises to {current_bet}.")
        elif action == "allin":
            total = player.stack
            player.bet += total
            game.pot += total
            player.stack = 0
            if player.bet > current_bet:
                current_bet = player.bet
                last_raiser = player
            print(f"{player.name} goes all-in ({player.bet}).")

        idx += 1
        # stop when everyone has called or folded after last raise
        if last_raiser and players[(idx % len(players))] == last_raiser:
            break

    return current_bet


# --- Game Flow ---
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
    print("\n--- Preflop Betting ---")
    current_bet = game.big_blind
    betting_round(game, current_bet)

    # Flop
    game.deal_flop()
    print("\nFlop:", cards_str(game.board))
    betting_round(game, 0)

    # Turn
    game.deal_turn()
    print("\nTurn:", cards_str(game.board))
    betting_round(game, 0)

    # River
    game.deal_river()
    print("\nRiver:", cards_str(game.board))
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
