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



## how to run
    run the __notesserver.py__ script.
    Optionally, the following parameters can be configured via a config.json file:
         PORT = config.get("PORT", 5000)
         NOTEBOOK_PATH = Path(config.get("NOTEBOOK_PATH", ".")).resolve()
         NOTEBOOK_NAME = config.get("NOTEBOOK_NAME", NOTEBOOK_PATH.name)
         BASIC_SECRET = config.get("BASIC_SECRET", None)
         DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS = config.get('DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS', 2)
         JOURNAL_ENTRY_DATE_FORMAT = config.get('JOURNAL_ENTRY_DATE_FORMAT', '%a %d.%m. %H:%M')
         SORT_TAGS_BY_NAME = config.get('SORT_TAGS_BY_NAME', False)
         SHOW_DOTFILES = config.get('SHOW_DOTFILES', False)
         EDITOR_COMMAND_LIST = config.get("EDITOR_COMMAND_LIST", [code_cmd, "{filepath}"])
         EDITOR_GOTO_COMMAND_LIST = config.get("EDITOR_GOTO_COMMAND_LIST", [code_cmd, "--goto", "{filepath}:{line_no}"])

         INDEX_PAGE_NAME = config.get("INDEX_PAGE_NAME", "index.md")   # set to None to disable index page special handling
         NO_JOURNAL_ENTRIES_ON_INDEX_PAGES = config.get("NO_JOURNAL_ENTRIES_ON_INDEX_PAGES", False)

         JOURNAL_PATH = NOTEBOOK_PATH / config.get("JOURNAL_PATH", "journal")
         MEDIA_PATH = NOTEBOOK_PATH / config.get("MEDIA_PATH", "media")

         NO_ADDITIONAL_TAGS = config.get("NO_ADDITIONAL_TAGS", "[only selected tags]")
         INCLUDE_SUBTAGS = config.get("INCLUDE_SUBTAGS", True)

   Set the environment variable NOTESSERVER_CONFIG_FILE, pointing to the config file that shall be loaded during startup.

   