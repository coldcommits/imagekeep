# imagekeep

Small desktop python app for sorting through photo folders. Pick folder, and it goes through every image one at a time and you can choose to keep or delete it. Deleted images go to your Trash Bin. **You must confirm delete in your trash can.**
Works on Windows so far.

## Features

- Pick folder
- Image preview that **should** scale with the window
- Delete button moves to Trash Bin (using [Send2Trash](https://github.com/arsenetar/send2trash)), you confirm in your OS
- Undo keep/delete
- Summary at the end like Spotify Wrapped :D
- Supports JPG, PNG, GIF, BMP, WEBP, TIFF (+ HEIC with `pillow-heif`) **You need to uncomment this in requirements.txt**

## Install

Requires Python 3.8+ with Tkinter (included with the python.org installers; on Debian/Ubuntu run `sudo apt install python3-tk`).

```bash
git clone https://github.com/coldcommits/imagekeep.git
cd imagekeep
pip install -r requirements.txt
```

## Use

```bash
py image_sorter.py
```

## Shortcut Keys

Nothing so far :( coming soon


## License

MIT
