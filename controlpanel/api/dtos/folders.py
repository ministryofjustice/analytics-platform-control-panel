from dataclasses import dataclass, field
import re
from typing import Optional
from pathlib import Path, PurePath
from glob import glob
import pathlib


FOLDER_PATTERN = r"([a-z0-9_-]{1,63}|\@)"
FOLDER_REGEX = re.compile(FOLDER_PATTERN)

def get_folder(folder: str, bucket: str) -> str:
    return folder.replace(bucket, '')


# f1 = FolderCheck('/exeter/bournmouth/token')
# f2 = FolderCheck('/exeter/')

# f1.is_child(f2)


@dataclass
class FolderCheck:
    value: str

    def _change_wildcards(self, insert_pure, existing_pure):

        for index, value in enumerate(insert_pure):
            if existing_pure[index] == '*':
                insert_pure[index] = '*'
            if value == '*':
                existing_pure[index] = '*'
        
        return insert_pure, existing_pure

    def is_parent(self, existing: "FolderCheck"):
        insert_pure = list(PurePath(self.value).parts)
        existing_pure = list(PurePath(existing.value).parts)

        if len(insert_pure) <= len(existing_pure):
            insert_pure, existing_pure = self._change_wildcards(list(insert_pure), list(existing_pure))
        
        return insert_pure == existing_pure[:len(insert_pure)]


    def is_child(self, existing: "FolderCheck"):
        insert_pure = list(PurePath(self.value).parts)
        existing_pure = list(PurePath(existing.value).parts)
        length = len(insert_pure)

        if insert_pure == existing_pure:
            return False

        # wildcards should be ran after to make sure that the * can match 
        if len(insert_pure) >= len(existing_pure):
            insert_pure, existing_pure = self._change_wildcards(insert_pure, existing_pure)

        for num, unit in enumerate(existing_pure[:length]):
            if unit == '*' or insert_pure[num] == '*':
                continue

            if unit != insert_pure[num]:
                return False
        return True
