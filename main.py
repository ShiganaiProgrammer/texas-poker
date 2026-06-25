import flet as ft
from poker_engine import GameState

CARD_W = 80
CARD_H = 114


def make_card_img(web):
    def card_img(rank, suit, face_up=True):
        ext = "png" if web else "svg"
        src = f"/images/{rank}_{suit}.{ext}" if face_up else "/images/card_back.png"
        return ft.Container(
            width=CARD_W, height=CARD_H,
            content=ft.Image(src=src),
            border_radius=5,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK_38, offset=ft.Offset(1, 2)),
        )
    return card_img


def make_card_row(web):
    img = make_card_img(web)
    def card_row(cards, face_up=True):
        return ft.Row(spacing=4, controls=[img(c.rank, c.suit, face_up) for c in cards])
    return card_row


def make_player_panel(web):
    row = make_card_row(web)
    def player_panel(p, phase):
        if p.eliminated:
            return ft.Container(
                bgcolor="#333333", border_radius=10, padding=8,
                content=ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Text(p.name, color=ft.Colors.GREY, weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(height=CARD_H + 4),
                    ft.Text("脱落", color=ft.Colors.GREY, weight=ft.FontWeight.BOLD, size=16),
                ]),
            )
        label = p.name + ("（フォールド）" if p.folded else "")
        cards = row(p.hole, phase == "showdown") if p.hole else ft.Container(height=CARD_H + 4)
        return ft.Container(
            bgcolor="#1B5E20", border_radius=10, padding=8,
            content=ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Text(label, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=14),
                cards,
                ft.Text(f"${p.chips}", color=ft.Colors.YELLOW_300, weight=ft.FontWeight.BOLD, size=16),
            ]),
        )
    return player_panel


def play_sound(page, src):
    try:
        a = ft.Audio(src=src, autoplay=True)
        page.overlay.append(a)
        page.update()
    except Exception:
        pass


@ft.component
def App():
    page = ft.context.page
    page.title = "Texas Hold'em Poker"
    page.padding = 10
    page.bgcolor = "#1B5E20"
    page.window.width = 900
    page.window.height = 700

    game, set_game = ft.use_state(lambda: GameState())
    counter, set_counter = ft.use_state(0)
    sound_played, set_sound_played = ft.use_state(False)

    card_img = make_card_img(page.web)
    card_row = make_card_row(page.web)
    player_panel = make_player_panel(page.web)

    def handle_new_game(e):
        set_sound_played(False)
        g = GameState()
        g.reset()
        set_game(g)
        set_counter(counter + 1)
        play_sound(page, "/sounds/se_card.mp3")

    def handle_next_hand(e):
        chips = [p.chips for p in game.players]
        g = GameState()
        g.dealer_idx = game.dealer_idx
        for i, p in enumerate(g.players):
            p.chips = chips[i]
        g.new_hand()
        while g.phase not in ("idle", "showdown") and g.players[g.current_player_idx].is_active and not g.players[g.current_player_idx].is_human:
            g.ai_act()
        set_sound_played(False)
        set_game(g)
        set_counter(counter + 1)
        play_sound(page, "/sounds/se_card.mp3")

    def handle_keyboard(e):
        key = e.key.lower()
        if key == "enter" and g.phase == "showdown":
            handle_next_hand(e)
            return
        if not human_turn or g.phase in ("idle", "showdown"):
            return
        if key == "a":
            handle_action("fold")
        elif key == "s":
            handle_action("call")
        elif key == "d":
            handle_action("raise", g.current_bet + g.big_blind * 2)

    page.on_keyboard_event = handle_keyboard

    def handle_action(action, raise_amt=0):
        g = game
        prev_phase = g.phase
        if g.phase in ("idle", "showdown"):
            return
        g.act(action, raise_amt)
        while g.phase not in ("idle", "showdown") and g.players[g.current_player_idx].is_active and not g.players[g.current_player_idx].is_human:
            g.ai_act()
        set_game(g)
        set_counter(counter + 1)
        if g.phase == "showdown" and prev_phase != "showdown" and not sound_played:
            set_sound_played(True)
            play_sound(page, "/sounds/se_win.mp3")

    g = game
    ap = g.current_player()
    human_turn = ap is not None and ap.is_human
    call_cost = g.current_bet - g.players[0].current_bet if g.phase not in ("idle", "showdown") else 0
    show = g.phase not in ("idle", "showdown")

    buttons = [
        ft.Button("新規ゲーム", on_click=handle_new_game),
    ]
    if show:
        buttons += [
            ft.Button("[A] フォールド", on_click=lambda e: handle_action("fold"), disabled=not human_turn),
            ft.Button("[S] チェック" if call_cost == 0 else f"[S] コール ${call_cost}", on_click=lambda e: handle_action("call"), disabled=not human_turn),
            ft.Button(f"[D] レイズ ${g.big_blind * 2}", on_click=lambda e: handle_action("raise", g.current_bet + g.big_blind * 2), disabled=not human_turn),
        ]

    result_info = None
    if g.phase == "showdown":
        win = "あなた" in (g.winner or "")
        result_info = ft.Container(
            bgcolor="#2E7D32" if win else "#C62828",
            border_radius=8,
            padding=ft.Padding(12, 4, 12, 4),
            content=ft.Row(spacing=8, controls=[
                ft.Column(spacing=2, controls=[
                    ft.Text("勝ち！" if win else "負け",
                            color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(g.message, color=ft.Colors.WHITE, size=11),
                ]),
                ft.Button("[Enter] 次へ", on_click=handle_next_hand),
            ]),
        )

    button_controls = [ft.Row(spacing=10, controls=buttons, expand=True)]
    if result_info:
        button_controls.append(result_info)

    controls = [
        ft.Row(controls=[player_panel(p, g.phase) for p in g.players[1:]], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        ft.Text(g.message, color=ft.Colors.WHITE, size=16),
        card_row(g.community, True),
        ft.Text(f"ポット: ${g.pot}", color=ft.Colors.YELLOW_300, size=20),
        card_row(g.players[0].hole, True),
        ft.Text(f"あなた: ${g.players[0].chips}", color=ft.Colors.WHITE, size=16),
        ft.Row(controls=button_controls),
    ]

    return ft.Column(spacing=10, controls=controls)


def main(page: ft.Page):
    page.render(App)


if __name__ == "__main__":
    ft.run(main)
