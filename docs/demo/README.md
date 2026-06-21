# Demo assets — multi-bot-agentic

## GIF / screen recording

Generate a demo GIF for the README:

```bash
# Example (requires asciinema + agg, or use scripts/render_demo_gif.py if present)
./scripts/run_demo.sh
python scripts/render_demo_gif.py --output docs/demo/demo.gif
```

Embed in README:

```markdown
![Agent demo](docs/demo/demo.gif)
```

## What to show

1. Agent receives goal / clinical query / paper question
2. ODA loop: observe → decide (rationale logged) → act
3. LLM adapter call (GPT / Claude / Gemini / Kimi)
4. Final output with audit/event log reference
