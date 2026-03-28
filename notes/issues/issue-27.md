https://github.com/con/yolo/issues/27

# Include/setup mcp server for driving/testing in a browser

not yet sure what is the best setup, but needed for any web ui driven development or documentation websites. Some hits:

- https://developer.chrome.com/blog/chrome-devtools-mcp
- https://www.reddit.com/r/ClaudeAI/comments/1jf4hnt/setting_up_mcp_servers_in_claude_code_a_tech/

not yet 100% sure we could do it in the container (which imho would be better for "fully packaged setup") as opposed to some local `~/.local` setup so claude from container just picks it up

edit: while working on https://github.com/yarikoptic/strava-backup it seemed to do pretty well (without mcp) although not sure if actually ran any playwright, and then stated

```
  I was unable to test it fully because the environment is missing system libraries for Playwright. You'll need to run:

  sudo playwright install-deps chromium
```

so may be that is what we need - just to install playwright and install chromium with it inside container? to be tested...
