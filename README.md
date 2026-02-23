# py-markdown-journal - lightweight wiki+blogging software for markdown-based journaling

## Idea
this software aims to provide a tool for organizing your knowledge base:

  1) a wiki for your knowledge base
     
     organize notes in markdown files
  2) collecting meeting minutes and other notes on-the-fly
     
     When jotting down your (meeting) notes, you usually don't have the time to think much about where exactly to put them and how to organize your notes.
     This small tool enables you to simply write down all of your meeting minutes, ideas, thoughts, and other notes in chronological order, in one simple file (or more files, if you prefer).
     Instead of thinking about file structures, you simply put it in one place and tag your daily notes.
     
     All words starting with an "x" are considered as a **tag**, e.g., by adding the word "xideas" somewhere in your journal, the respective tag is assigned to that journal entry.



## dependencies
<code>
apt-get install python3-markdown-it python3-mdit-py-plugins python3-flask python3-watchdog gunicorn
... or pip3 install markdown-it-py[linkify,plugins]; pip3 install flask; pip3 install watchdog
</code>

## how to run
<code>
cd YOUR-MARKDOWN-FOLDER
export NOTESSERVER\_CONFIG\_FILE=.config.json (optional, if you'd like to specify a config file)
</code>

Then,
- run the __notesserver__ module: PYTHONPATH=PATH-TO-PY-MARKDOWN-JOURNAL-PROJECT python3 -m notesserver 5000
- ... or, use waitress:
  PYTHONPATH=PATH-TO-PY-MARKDOWN-JOURNAL-PROJECT waitress-serve --listen=localhost:5000 --call notesserver:create\_app
- ... or, use gunicorn:
  gunicorn -w 2 -b 127.0.0.1:5000 --pythonpath PATH-TO-PY-MARKDOWN-JOURNAL-PROJECT "notesserver:create\_app()"


## configuration
    Optionally, a config file can be provided. Therefore, set the NOTESSERVER\_CONFIG\_FILE environment variable, pointing to the path of that config file. The following parameters can be specified:

      NOTEBOOK_PATH = Path(config.get("NOTEBOOK_PATH", ".")).resolve()
      NOTEBOOK_NAME = config.get("NOTEBOOK_NAME", NOTEBOOK_PATH.name)
      BASIC_SECRET = config.get("BASIC_SECRET", None)
      DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS = config.get('DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS', 2)
      JOURNAL_ENTRY_DATE_FORMAT = config.get('JOURNAL_ENTRY_DATE_FORMAT', '%a %d.%m. %H:%M')

      NEW_JOURNAL_ENTRY_DEFAULT_TAGS_LIST = config.get('NEW_JOURNAL_ENTRY_DEFAULT_TAGS_LIST', ["inbox"])
      SORT_TAGS_BY_NAME = config.get('SORT_TAGS_BY_NAME', False)
      HIDE_DOTFILES = config.get('HIDE_DOTFILES', True)

      EDITOR_COMMAND_LIST = _set_editor_path(command_list=config.get("EDITOR_COMMAND_LIST", ["code", "{filepath}"]))
      EDITOR_GOTO_COMMAND_LIST = _set_editor_path(command_list=config.get("EDITOR_GOTO_COMMAND_LIST", ["code", "--goto", "{filepath}:{line_no}"]))

      ALT_EDITOR_COMMAND_LIST = _set_editor_path(command_list=config.get("ALT_EDITOR_COMMAND_LIST", EDITOR_COMMAND_LIST))
      ALT_EDITOR_GOTO_COMMAND_LIST = _set_editor_path(command_list=config.get("ALT_EDITOR_GOTO_COMMAND_LIST", EDITOR_GOTO_COMMAND_LIST))

      INDEX_PAGE_NAME = config.get("INDEX_PAGE_NAME", "index.md")   # set to None to disable index page special handling
      NO_JOURNAL_ENTRIES_ON_INDEX_PAGES = config.get("NO_JOURNAL_ENTRIES_ON_INDEX_PAGES", False)

      JOURNAL_PATH = NOTEBOOK_PATH / config.get("JOURNAL_PATH", "journal")
      MEDIA_PATH = NOTEBOOK_PATH / config.get("MEDIA_PATH", "media")

      NO_ADDITIONAL_TAGS = config.get("NO_ADDITIONAL_TAGS", "[only selected tags]")
      INCLUDE_SUBTAGS = config.get("INCLUDE_SUBTAGS", True)

