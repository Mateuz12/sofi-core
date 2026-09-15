from dataclasses import dataclass
from typing import Any, List, Optional
import json

@dataclass
class DiffEntry:
    chave: str
    valor_anterior: Optional[str]
    valor_novo: Optional[str]

def _serialize_val(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)

def compute_diff(old_dict: Any, new_dict: Any, prefix: str = '') -> List[DiffEntry]:
    diffs: List[DiffEntry] = []

    if isinstance(old_dict, dict) and isinstance(new_dict, dict):
        all_keys = set(old_dict.keys()).union(set(new_dict.keys()))
        for k in sorted(all_keys):
            curr_path = f'{prefix}.{k}' if prefix else str(k)
            if k not in old_dict:
                diffs.append(DiffEntry(
                    chave=curr_path,
                    valor_anterior=None,
                    valor_novo=_serialize_val(new_dict[k])
                ))
            elif k not in new_dict:
                diffs.append(DiffEntry(
                    chave=curr_path,
                    valor_anterior=_serialize_val(old_dict[k]),
                    valor_novo=None
                ))
            else:
                diffs.extend(compute_diff(old_dict[k], new_dict[k], curr_path))

    elif isinstance(old_dict, list) and isinstance(new_dict, list):
        max_len = max(len(old_dict), len(new_dict))
        for i in range(max_len):
            curr_path = f'{prefix}[{i}]'
            if i >= len(old_dict):
                diffs.append(DiffEntry(
                    chave=curr_path,
                    valor_anterior=None,
                    valor_novo=_serialize_val(new_dict[i])
                ))
            elif i >= len(new_dict):
                diffs.append(DiffEntry(
                    chave=curr_path,
                    valor_anterior=_serialize_val(old_dict[i]),
                    valor_novo=None
                ))
            else:
                diffs.extend(compute_diff(old_dict[i], new_dict[i], curr_path))

    else:
        if old_dict != new_dict:
            diffs.append(DiffEntry(
                chave=prefix,
                valor_anterior=_serialize_val(old_dict),
                valor_novo=_serialize_val(new_dict)
            ))

    return diffs
