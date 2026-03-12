#!/usr/bin/env python
"""
scripts/cleanup_spam_lists.py

One-time cleanup script for spam lists (issue #11905).
Finds all list documents whose name or description match spam words
and marks them as deleted in the database.

Our dump analysis found:
  - 254,050 total lists
  - 13,740 spam + zero-seed lists (high confidence)
  - Top spam: casino (1,163), pharma (1,173), phone scams (1,759)

Usage:
    python scripts/cleanup_spam_lists.py --dry-run   # preview only
    python scripts/cleanup_spam_lists.py             # actually delete
"""

import argparse
import re
import sys

import web

# Bootstrap the openlibrary app context
sys.path.insert(0, '.')
import infogami
from infogami import config

config.db_parameters = {'dbn': 'postgres', 'db': 'openlibrary'}
infogami._setup()


def get_spam_words() -> list[str]:
    doc = web.ctx.site.store.get("spamwords") or {}
    return doc.get("spamwords", [])


def is_spam_list_content(name: str, description: str, spam_words: list[str]) -> bool:
    text = f"{name} {description}".lower()
    return any(re.search(w.lower(), text) for w in spam_words)


def find_spam_lists(spam_words: list[str]) -> list[dict]:
    """Query all lists and return those matching spam words."""
    spam_lists = []
    offset = 0
    batch_size = 1000
    while True:
        results = web.ctx.site.things(
            {'type': '/type/list', 'limit': batch_size, 'offset': offset}
        )
        if not results:
            break
        for key in results:
            doc = web.ctx.site.get(key)
            if doc is None:
                continue
            name = doc.get('name') or ''
            description = str(doc.get('description') or '')
            if is_spam_list_content(name, description, spam_words):
                spam_lists.append({'key': key, 'name': name})
        offset += batch_size
    return spam_lists


def delete_list(key: str) -> None:
    """Mark a list as deleted."""
    doc = {'key': key, 'type': {'key': '/type/delete'}}
    web.ctx.site.save(doc, action='lists', comment='Spam cleanup (#11905)')


def main():
    parser = argparse.ArgumentParser(description='Clean up spam lists')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be deleted without deleting',
    )
    args = parser.parse_args()

    spam_words = get_spam_words()
    if not spam_words:
        print("No spam words configured. Exiting.")
        return

    print(f"Scanning for spam lists using {len(spam_words)} spam words...")
    spam_lists = find_spam_lists(spam_words)
    print(f"Found {len(spam_lists)} spam lists.")

    for item in spam_lists:
        action = '[DRY RUN] Would delete' if args.dry_run else 'Deleting'
        print(f"  {action}: {item['key']} — \"{item['name']}\"")
        if not args.dry_run:
            delete_list(item['key'])

    if not args.dry_run:
        print("Done. Re-run the Solr indexer to remove from search results.")


if __name__ == '__main__':
    main()
