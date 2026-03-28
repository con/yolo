https://github.com/con/yolo/issues/36

# Makes current directory $HOME thus leading to appearance of various folders

like `~/.cache` , `~/.npm` and others in current folder ... should not be happening!  likely needs to do what we do in repronim/containers and create a fake (tmp) folder to be bind mounted as HOME, unless we want it persistent and thus, if started where there is .git, could be `.git/yolo/home` or alike
