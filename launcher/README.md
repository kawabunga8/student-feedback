# Desktop launcher

`~/Desktop/Student Feedback.app` starts light mode (`../start.sh`: Ollama + the feedback app, no Docker/Course Hub),
opens the page, and on the next click offers Open / Stop.

Rebuild (e.g. if the repo moves): edit the paths in `launcher.applescript`, then
```bash
osacompile -o "$HOME/Desktop/Student Feedback.app" launcher/launcher.applescript
```
and re-add the icon (render `icon.svg` to a 1024px transparent PNG, build an .icns with `iconutil`, copy it to
`Contents/Resources/applet.icns`, delete `Contents/Resources/Assets.car` and the `CFBundleIconName` key from
`Info.plist`, then `xattr -cr` and `codesign --force --deep -s -` the app).
