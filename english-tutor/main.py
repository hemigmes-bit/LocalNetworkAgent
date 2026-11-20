import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from config import DB_PATH, load_config
from db import Store
from providers import chat, make_client, parse_json
from srs import review as sm2
from tutor import Tutor
import voice

console = Console()

HELP = """[bold]Commands[/bold]
Enter (empty)              Speak into the microphone
/level A1..C2              Change your CEFR level
/mode free|roleplay|grammar|vocab [topic]
                           Change practice mode (optional scenario/topic)
/review                    Vocabulary review with spaced repetition
/stats                     Show your progress
/recap                     End-of-session metacognitive review
/recommend                 Show learning recommendations
/progress                  Show level progress and mastery
/curriculum                Show curriculum for current level
/levelup                   Check if ready for next level
/voice                     Toggle spoken replies on/off
/speed 1.2                 Change speaking speed (1.0 normal, 2.0 max; or +30% for edge)
/repeat                    Repeat the last reply aloud
/listen                   Toggle hands-free voice detection (start talking = turn)
/help                      Show this help
/quit                      Exit (saves recap)"""


def show_feedback(result):
    for c in result["corrections"]:
        console.print(
            f"  [yellow]correction:[/yellow] {c.get('original')} -> [green]{c.get('corrected')}[/green]"
        )
        if c.get("explanation"):
            console.print(f"    [dim]{c.get('explanation')}[/dim]")
    for v in result["new_vocabulary"]:
        console.print(
            f"  [cyan]new word:[/cyan] {v.get('word')} [dim]({v.get('translation')})[/dim]"
        )


def review_session(store, client, cfg):
    due = store.due_vocab(limit=20)
    if not due:
        console.print("[green]No vocabulary due for review. Keep talking![/green]")
        return
    console.print(f"\n[bold]Vocabulary review[/bold] - {len(due)} card(s) due\n")
    for item in due:
        console.print(
            Panel(
                f"[bold cyan]{item['word']}[/bold cyan]\n[dim]{item['example'] or ''}[/dim]",
                title="Translate into English",
            )
        )
        answer = Prompt.ask("Your answer (or Enter to skip)")
        if not answer.strip():
            console.print(f"  [dim]Skipped. Answer: {item['translation']}[/dim]")
            quality = 2
        else:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Judge if the student's answer matches the expected translation or meaning. "
                        'Return ONLY JSON: {"correct": true} or {"correct": false}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Word: {item['word']}\nExpected: {item['translation']}\n"
                        f"Student answer: {answer}"
                    ),
                },
            ]
            data = parse_json(chat(client, cfg, messages, temperature=0.0)) or {}
            correct = bool(data.get("correct"))
            quality = 5 if correct else 2
            if correct:
                console.print("  [green]Correct![/green]")
            else:
                console.print(
                    f"  [red]Not quite.[/red] Expected: [bold]{item['translation']}[/bold]"
                )
        ease, interval_days, reps, next_review = sm2(
            item["ease"], item["interval_days"], item["repetitions"], quality
        )
        store.update_vocab(item["id"], ease, interval_days, reps, next_review)
        console.print(f"  [dim]Next review in {interval_days} day(s)[/dim]\n")


def show_stats(store):
    learner = store.learner()
    vs = store.vocab_stats()
    table = Table(title="Your progress")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Name", learner["name"])
    table.add_row("CEFR level", learner["level"])
    table.add_row("Sessions", str(store.session_count()))
    table.add_row("Vocabulary cards", str(vs["total"]))
    table.add_row("Due now", str(vs["due"]))
    table.add_row("Learned (3+ reps)", str(vs["learned"]))
    console.print(table)
    errors = store.recent_error_types()
    if errors:
        console.print("[bold]Top mistake patterns:[/bold]")
        for e in errors:
            console.print(f"  - {e['error_type']}: {e['n']}")


def print_recap(data):
    if not data:
        return
    if data.get("message"):
        console.print(Panel(str(data["message"]), title="Session recap"))
    if data.get("focus_next"):
        console.print("[bold]Next session focus:[/bold] " + "; ".join(data["focus_next"]))
    if data.get("errors"):
        console.print("[bold]Mistakes to review:[/bold] " + "; ".join(map(str, data["errors"])))


def voice_turn(cfg):
    while True:
        result = voice.listen_auto(cfg)
        kind = result[0]
        if kind == "key":
            ch = result[1]
            if ch in ("\r", "\n"):
                return ("text", "")
            if ch in ("\x1b", "\x03"):
                return ("quit", None)
            rest = input()
            return ("text", ch + rest)
        if kind == "noise":
            continue
        audio = result[1]
        try:
            user, lang = voice.transcribe(audio, cfg)
        except Exception as exc:
            return ("error", f"Transcription error: {exc}")
        if not user:
            continue
        return ("text", user, lang)


def main():
    args = sys.argv[1:]
    cfg = load_config()
    store = Store(DB_PATH)
    learner = store.ensure_learner(cfg["student_name"], cfg["level"], cfg["native_language"])
    client = make_client(cfg)
    session_id = store.start_session("free")
    tutor = Tutor(store, client, cfg, session_id)

    if "--once" in args:
        idx = args.index("--once")
        text = args[idx + 1] if len(args) > idx + 1 else "Hello!"
        result = tutor.turn(text)
        print(result["reply"])
        for c in result["corrections"]:
            print(f"CORRECTION: {c.get('original')} -> {c.get('corrected')} ({c.get('explanation')})")
        for v in result["new_vocabulary"]:
            print(f"VOCAB: {v.get('word')} = {v.get('translation')}")
        if "--recap" in args:
            recap = tutor.recap() or {}
            for key in ("topics", "strengths", "errors", "focus_next", "message"):
                print(f"RECAP_{key.upper()}: {recap.get(key)}")
        return

    console.print(
        Panel.fit(
            f"[bold]English Tutor[/bold] - level [cyan]{learner['level']}[/cyan], mode [cyan]free[/cyan]\n"
            f"Provider: {cfg['provider']} / {cfg['model']}\n"
            "Hands-free: just start talking. Press any key to type a command.\n"
            "Type [bold]/help[/bold] for commands.",
            title="Emma",
        )
    )

    recapped = False
    last_reply = ""
    user_lang = "en"
    try:
        while True:
            if cfg.get("voice_auto", True):
                kind, *rest = voice_turn(cfg)
                if kind == "quit":
                    break
                if kind == "error":
                    console.print(f"[red]{rest[0]}[/red]")
                    continue
                user = rest[0]
                if len(rest) > 1:
                    user_lang = rest[1]
                else:
                    user_lang = "en"
                if not user.strip():
                    continue
            else:
                try:
                    user = Prompt.ask("[bold blue]You[/bold blue] [dim](Enter=voz)[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break
                if not user.strip():
                    if not cfg.get("voice", True):
                        continue
                    console.print("[dim]Listening... speak now.[/dim]")
                    try:
                        audio = voice.record(cfg)
                    except Exception as exc:
                        console.print(f"[red]Microphone error: {exc}[/red]")
                        continue
                    if audio is None:
                        console.print("[yellow]No speech detected.[/yellow]")
                        continue
                    console.print("[dim]Transcribing...[/dim]")
                    try:
                        user, user_lang = voice.transcribe(audio, cfg)
                    except Exception as exc:
                        console.print(f"[red]Transcription error: {exc}[/red]")
                        continue
                    if not user:
                        console.print("[yellow]I did not catch that, try again.[/yellow]")
                        continue
                    console.print(f"[bold blue]You (voice)[/bold blue]: {user}")
            if user.startswith("/"):
                parts = user.split(maxsplit=2)
                cmd = parts[0].lower()
                if cmd in ("/quit", "/exit", "/q"):
                    break
                if cmd == "/help":
                    console.print(Panel(HELP))
                elif cmd == "/level":
                    valid = ("A1", "A2", "B1", "B2", "C1", "C2")
                    if len(parts) > 1 and parts[1].upper() in valid:
                        store.set_level(parts[1].upper())
                        console.print(f"[green]Level set to {parts[1].upper()}[/green]")
                    else:
                        console.print(
                            f"[red]Current level: {store.learner()['level']}. Usage: /level B2[/red]"
                        )
                elif cmd == "/mode":
                    valid = ("free", "roleplay", "grammar", "vocab")
                    if len(parts) > 1 and parts[1].lower() in valid:
                        topic = parts[2] if len(parts) > 2 else ""
                        tutor.set_mode(parts[1].lower(), topic)
                        console.print(f"[green]Mode: {parts[1].lower()} {topic}[/green]")
                    else:
                        console.print("[red]Usage: /mode free|roleplay|grammar|vocab [topic][/red]")
                elif cmd == "/review":
                    review_session(store, client, cfg)
                elif cmd == "/stats":
                    show_stats(store)
                elif cmd == "/voice":
                    cfg["voice"] = not cfg.get("voice", True)
                    state = "ON" if cfg["voice"] else "OFF"
                    console.print(f"[green]Voice replies: {state}[/green]")
                elif cmd == "/listen":
                    cfg["voice_auto"] = not cfg.get("voice_auto", True)
                    state = "ON" if cfg["voice_auto"] else "OFF"
                    console.print(f"[green]Hands-free (start talking = turn): {state}[/green]")
                elif cmd == "/speed":
                    if len(parts) > 1 and parts[1].endswith("%"):
                        value = parts[1] if parts[1][0] in "+-" else "+" + parts[1]
                        cfg["tts_rate"] = value
                        console.print(f"[green]Edge speed: {value}[/green]")
                    elif len(parts) > 1:
                        try:
                            cfg["tts_speed"] = float(parts[1])
                            console.print(f"[green]Speed: {parts[1]}x[/green]")
                        except ValueError:
                            console.print("[red]Usage: /speed 1.3 or /speed +30%[/red]")
                    else:
                        console.print(
                            f"[red]Current: {cfg.get('tts_speed', 1.0)}x (edge: {cfg.get('tts_rate', '+40%')}). "
                            "Usage: /speed 1.3[/red]"
                        )
                elif cmd == "/repeat":
                    if last_reply:
                        try:
                            voice.speak(last_reply, cfg, lang=user_lang)
                        except Exception as exc:
                            console.print(f"[red]TTS error: {exc}[/red]")
                    else:
                        console.print("[yellow]Nothing to repeat yet.[/yellow]")
                elif cmd == "/progress":
                    summary = tutor.get_progress_summary()
                    if summary:
                        console.print(Panel(f"[bold]Level: {summary['current_level']}[/bold]\n"
                            f"Avg mastery: {summary['mastery_avg']:.0%}\n"
                            f"Sessions: {summary['sessions_at_level']}\n"
                            f"Vocab: {summary['vocab_count']}\n"
                            f"Next level: {summary['next_level'] or 'C2 (max)'}\n"
                            f"Ready: {'YES' if summary['ready_for_level_up'] else 'Not yet'}", title="Progress"))
                        for cat, val in summary["mastery"].items():
                            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                            console.print(f"  {cat:12} {bar} {val:.0%}")
                        if summary["recommendations"]:
                            console.print("[bold]Focus areas:[/bold]")
                            for r in summary["recommendations"]:
                                console.print(f"  - {r['category']}: {r['item']} ({r['reason']})")
                    else:
                        console.print("[yellow]Level progression not enabled.[/yellow]")
                elif cmd == "/curriculum":
                    from level_progression import CURRICULUM
                    level = store.learner()["level"]
                    curr = CURRICULUM.get(level, {})
                    console.print(Panel(f"[bold]Curriculum for {level}[/bold]", title="Curriculum"))
                    for cat, items in curr.items():
                        console.print(f"[bold]{cat.upper()}:[/bold] {', '.join(items)}")
                elif cmd == "/levelup":
                    level = store.learner()["level"]
                    from level_progression import LevelProgression
                    prog = LevelProgression(DB_PATH)
                    next_l = prog.check_level_up(level)
                    if next_l:
                        console.print(f"[green]READY for {next_l}![/green] (auto-advances on next turn)")
                    else:
                        console.print(f"[yellow]Not ready for next level yet.[/yellow]")
                        summary = prog.get_status_summary(level)
                        for cat, val in summary["mastery"].items():
                            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                            console.print(f"  {cat:12} {bar} {val:.0%}")
                elif cmd == "/recommend":
                    recs = tutor.get_recommendations(5)
                    if recs:
                        console.print("[bold]Recommended focus:[/bold]")
                        for r in recs:
                            console.print(f"  - {r['category']}: {r['item']} ({r['reason']})")
                    else:
                        console.print("[green]No specific recommendations - keep practicing![/green]")
                    console.print("[dim]Generating recap...[/dim]")
                    print_recap(tutor.recap())
                    recapped = True
                else:
                    console.print("[red]Unknown command. Type /help[/red]")
                continue
            try:
                result = tutor.turn(user)
            except Exception as exc:
                console.print(f"[red]Error: {exc}[/red]")
                continue
            console.print(f"[bold green]Emma[/bold green]: {result['reply']}\n")
            show_feedback(result)
            last_reply = result["reply"]
            if cfg.get("voice", True):
                try:
                    voice.speak(result["reply"], cfg, lang=user_lang)
                except Exception as exc:
                    console.print(f"[dim]TTS unavailable: {exc}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
    finally:
        if tutor.history and not recapped:
            console.print("\n[dim]Generating session recap...[/dim]")
            try:
                print_recap(tutor.recap())
            except Exception as exc:
                console.print(f"[red]Recap failed: {exc}[/red]")
        console.print("[bold]See you next time![/bold]")


if __name__ == "__main__":
    main()
