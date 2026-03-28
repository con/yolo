https://github.com/con/yolo/issues/54

# add support for openrouter users

at the moment, yolo expects that I have a claude code subscription - sadly I don't. But I have a bunch of credits in an openrouter account - and I can use claude code with openrouter.

I think this would be a relatively easy fix, afaict (and have tested locally), it just requires two extra ENV variables:

```bash

podman  run --log-driver=none -it --rm \
    ...
    -e ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
    -e ANTHROPIC_AUTH_TOKEN="${OPENROUTER_API_KEY}"
    ...
```

Would this go as an option into `setup.yolo`?
