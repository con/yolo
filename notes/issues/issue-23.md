https://github.com/con/yolo/issues/23

# Create collection of "skills" or prompts for typical use cases

e.g. currently trying smth like

```shell
❯ yolo "using the most recent logs of the test runs under .duct/logs/ please prepare to submit (using gh) an issue about failing tests against the repository of the 'origin' git remote. Before that check also for existing issues in that repo on whether already filed or relevant somehow present and to be mentioned in the new issue. While filing issue make sure to include information from 'git describe --tags' about the version of this package and how testing was done (from duct logs)"
```

so potentially we could establish a collection of similar prompts... in principle it is not yolo specific at all and there might be already such a project or we could create it outside of yolo and then use here...

## Comments

### asmacdo (2025-12-06T17:49:02Z)

Sounds like a job for a Claude code plugin!

https://code.claude.com/docs/en/plugins
