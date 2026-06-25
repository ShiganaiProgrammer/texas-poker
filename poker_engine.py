import random
from dataclasses import dataclass, field
from typing import Optional
from itertools import combinations

RANK_NAMES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
SUIT_NAMES = ["hearts", "diamonds", "clubs", "spades"]
RANK_VALUES = {name: i + 2 for i, name in enumerate(RANK_NAMES)}

HAND_NAMES_JP = {
    9: "ロイヤルフラッシュ",
    8: "ストレートフラッシュ",
    7: "フォーカード",
    6: "フルハウス",
    5: "フラッシュ",
    4: "ストレート",
    3: "スリーカード",
    2: "ツーペア",
    1: "ワンペア",
    0: "ハイカード",
}


@dataclass
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return RANK_VALUES[self.rank]

    def __str__(self):
        return f"{self.rank}_{self.suit}"


def create_deck() -> list[Card]:
    return [Card(r, s) for s in SUIT_NAMES for r in RANK_NAMES]


def eval_hand(hole: list[Card], community: list[Card]) -> tuple[int, list[int]]:
    best_score = (-1, [])
    all_cards = hole + community
    for combo in combinations(all_cards, 5):
        score = rank_hand(list(combo))
        if score > best_score:
            best_score = score
    return best_score


def rank_hand(cards: list[Card]) -> tuple[int, list[int]]:
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight, high = check_straight(values)
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    if is_flush and is_straight and high == 14:
        return (9, values)
    if is_flush and is_straight:
        return (8, [high])
    if groups[0][1] == 4:
        four = groups[0][0]
        kicker = groups[1][0]
        return (7, [four, kicker])
    if groups[0][1] == 3 and len(groups) > 1 and groups[1][1] == 2:
        return (6, [groups[0][0], groups[1][0]])
    if is_flush:
        return (5, values)
    if is_straight:
        return (4, [high])
    if groups[0][1] == 3:
        three = groups[0][0]
        kickers = sorted([v for v in values if v != three], reverse=True)
        return (3, [three] + kickers)
    if groups[0][1] == 2 and len(groups) > 1 and groups[1][1] == 2:
        pairs = sorted([g[0] for g in groups if g[1] == 2], reverse=True)
        kicker = [g[0] for g in groups if g[1] == 1][0]
        return (2, pairs + [kicker])
    if groups[0][1] == 2:
        pair = groups[0][0]
        kickers = sorted([v for v in values if v != pair], reverse=True)
        return (1, [pair] + kickers)
    return (0, values)


def check_straight(values: list[int]) -> tuple[bool, int]:
    vals = sorted(set(values), reverse=True)
    if len(vals) < 5:
        return False, 0
    for i in range(len(vals) - 4):
        if vals[i] - vals[i + 4] == 4:
            return True, vals[i]
    if 14 in vals and 2 in vals and 3 in vals and 4 in vals and 5 in vals:
        return True, 5
    return False, 0


@dataclass
class Player:
    name: str
    chips: int = 1000
    hole: list[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    current_bet: int = 0
    is_human: bool = False
    eliminated: bool = False

    @property
    def is_active(self) -> bool:
        return not self.eliminated and not self.folded and not self.all_in


@dataclass
class GameState:
    deck: list[Card] = field(default_factory=create_deck)
    community: list[Card] = field(default_factory=list)
    players: list[Player] = field(default_factory=lambda: [
        Player("あなた", is_human=True),
        Player("アリス"),
        Player("ボブ"),
        Player("キャロル"),
    ])
    pot: int = 0
    current_bet: int = 0
    phase: str = "idle"
    dealer_idx: int = 0
    current_player_idx: int = 0
    last_raiser_idx: Optional[int] = None
    small_blind: int = 10
    big_blind: int = 20
    message: str = "「新規ゲーム」を押して開始"
    winner: Optional[str] = None
    winning_hand: Optional[str] = None

    def _next_seat(self, start: int, skip: int = 1) -> int:
        idx = start
        found = 0
        for _ in range(len(self.players)):
            idx = (idx + 1) % len(self.players)
            if not self.players[idx].eliminated:
                found += 1
                if found >= skip:
                    return idx
        return start

    def reset(self):
        self.deck = create_deck()
        random.shuffle(self.deck)
        self.community = []
        for p in self.players:
            p.hole = []
            p.folded = False
            p.all_in = False
            p.current_bet = 0
            p.eliminated = False
            p.chips = 1000
        self.pot = 0
        self.current_bet = 0
        self.phase = "pre-flop"
        self.message = ""
        self.winner = None
        self.winning_hand = None
        self.last_raiser_idx = None
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        self._deal_holes()
        self._post_blinds()
        self.current_player_idx = (self.dealer_idx + 3) % len(self.players)

    def new_hand(self):
        self.deck = create_deck()
        random.shuffle(self.deck)
        self.community = []
        for p in self.players:
            if p.chips <= 0:
                p.eliminated = True
            p.hole = []
            p.folded = False
            p.all_in = False
            p.current_bet = 0

        remaining = [p for p in self.players if not p.eliminated]
        if len(remaining) <= 1:
            self.phase = "idle"
            self.winner = remaining[0].name if remaining else None
            self.message = f"{self.winner} の総合勝利！" if self.winner else ""
            return

        self.pot = 0
        self.current_bet = 0
        self.phase = "pre-flop"
        self.message = ""
        self.winner = None
        self.winning_hand = None
        self.last_raiser_idx = None
        self.dealer_idx = self._next_seat(self.dealer_idx, 1)
        self._deal_holes()
        self._post_blinds()
        bb_idx = self._next_seat(self.dealer_idx, 2)
        utg_idx = self._next_seat(bb_idx, 1)
        self.current_player_idx = utg_idx

    def _deal_holes(self):
        active = [p for p in self.players if not p.eliminated]
        for _ in range(2):
            for p in active:
                p.hole.append(self.deck.pop())

    def _post_blinds(self):
        sb_idx = self._next_seat(self.dealer_idx, 1)
        bb_idx = self._next_seat(sb_idx, 1)
        sb_amt = min(self.small_blind, self.players[sb_idx].chips)
        bb_amt = min(self.big_blind, self.players[bb_idx].chips)
        self.players[sb_idx].chips -= sb_amt
        self.players[sb_idx].current_bet = sb_amt
        self.players[bb_idx].chips -= bb_amt
        self.players[bb_idx].current_bet = bb_amt
        self.pot += sb_amt + bb_amt
        self.current_bet = bb_amt

    def deal_flop(self):
        self.deck.pop()
        for _ in range(3):
            self.community.append(self.deck.pop())
        self.phase = "flop"
        self._new_betting_round()

    def deal_turn(self):
        self.deck.pop()
        self.community.append(self.deck.pop())
        self.phase = "turn"
        self._new_betting_round()

    def deal_river(self):
        self.deck.pop()
        self.community.append(self.deck.pop())
        self.phase = "river"
        self._new_betting_round()

    def _new_betting_round(self):
        self.current_bet = 0
        for p in self.players:
            p.current_bet = 0
        active = [i for i, p in enumerate(self.players) if p.is_active]
        if active:
            self.current_player_idx = active[0]
            self.last_raiser_idx = None

    def act(self, action: str, raise_amount: int = 0) -> bool:
        p = self.players[self.current_player_idx]
        if not p.is_active:
            self._next_player()
            return True

        if self.last_raiser_idx is None:
            self.last_raiser_idx = self.current_player_idx

        if action == "fold":
            p.folded = True
            self.message = f"{p.name} がフォールド"
        elif action == "check":
            self.message = f"{p.name} がチェック"
        elif action == "call":
            call_amount = self.current_bet - p.current_bet
            call_amount = min(call_amount, p.chips)
            p.chips -= call_amount
            p.current_bet += call_amount
            self.pot += call_amount
            if p.chips == 0:
                p.all_in = True
            self.message = f"{p.name} が ${call_amount} コール"
        elif action == "raise":
            total = min(raise_amount, p.chips + p.current_bet)
            raise_chips = total - p.current_bet
            p.chips -= raise_chips
            p.current_bet = total
            self.pot += raise_chips
            self.current_bet = total
            self.last_raiser_idx = self.current_player_idx
            if p.chips == 0:
                p.all_in = True
            self.message = f"{p.name} が ${total} にレイズ"

        self._next_player()
        if self._betting_done():
            self._advance_phase()
        return True

    def _next_player(self):
        for _ in range(len(self.players)):
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
            p = self.players[self.current_player_idx]
            if not p.eliminated and p.is_active:
                return

    def _betting_done(self) -> bool:
        active = [i for i, p in enumerate(self.players) if p.is_active]
        if len(active) <= 1:
            return True
        if self.last_raiser_idx is None:
            return self.current_player_idx == active[0]
        return self.current_player_idx == self.last_raiser_idx

    def _advance_phase(self):
        active = [i for i, p in enumerate(self.players) if p.is_active]
        non_folded = [p for p in self.players if not p.folded and not p.eliminated]
        if len(active) == 0 or (len(active) == 1 and len(non_folded) > 1):
            while self.phase != "river":
                if self.phase == "pre-flop":
                    self.deal_flop()
                elif self.phase == "flop":
                    self.deal_turn()
                elif self.phase == "turn":
                    self.deal_river()
            self._go_to_showdown()
            return
        if len(active) == 1:
            self._go_to_showdown()
            return

        if self.phase == "pre-flop":
            self.deal_flop()
        elif self.phase == "flop":
            self.deal_turn()
        elif self.phase == "turn":
            self.deal_river()
        elif self.phase == "river":
            self._go_to_showdown()

    def _go_to_showdown(self):
        self.phase = "showdown"
        active = [p for p in self.players if not p.folded and not p.eliminated]
        if len(active) == 1:
            self.winner = active[0].name
            self.winning_hand = "最終対決"
            active[0].chips += self.pot
            self.message = f"{self.winner} が ${self.pot} 獲得！"
            return

        best_score = (-1, [])
        winners = []
        for p in active:
            score = eval_hand(p.hole, self.community)
            if score > best_score:
                best_score = score
                winners = [p]
            elif score == best_score:
                winners.append(p)

        split = self.pot // len(winners)
        rem = self.pot % len(winners)
        for i, w in enumerate(winners):
            w.chips += split + (1 if i < rem else 0)
        self.winner = ", ".join(w.name for w in winners)
        self.winning_hand = HAND_NAMES_JP.get(best_score[0], "不明")
        self.message = f"{self.winner} が ${self.pot} 獲得（{self.winning_hand}）"

    def current_player(self) -> Optional[Player]:
        if self.phase in ("idle", "showdown"):
            return None
        return self.players[self.current_player_idx]

    def ai_act(self):
        p = self.players[self.current_player_idx]
        if p.is_human or not p.is_active:
            return False

        total_cards = len(p.hole) + len(self.community)
        if total_cards < 5:
            v1 = max(c.value for c in p.hole)
            v2 = min(c.value for c in p.hole)
            suited = p.hole[0].suit == p.hole[1].suit
            if v1 == v2:
                strength = v1 * 0.6
            else:
                bonus = (1 if suited else 0) + (0.5 if abs(v1 - v2) <= 2 else 0)
                strength = (v1 + v2 + bonus) * 0.3
        else:
            rank, _ = eval_hand(p.hole, self.community)
            strength = rank

        call_cost = self.current_bet - p.current_bet

        if strength >= 6:
            raise_amt = min(self.current_bet * 3, p.chips + p.current_bet)
            if raise_amt <= p.current_bet:
                self.act("call")
            else:
                self.act("raise", raise_amt)
        elif strength >= 3:
            if call_cost <= self.big_blind * 2:
                self.act("call")
            else:
                self.act("fold")
        elif strength >= 1:
            if call_cost <= self.big_blind and random.random() < 0.4:
                self.act("call")
            else:
                self.act("fold")
        else:
            if call_cost == 0:
                self.act("check")
            else:
                self.act("fold")
        return True
