"""lib/themes · 生成站的可插拔主题库。

切换主题：在行业 config（industries/*.yaml）里写 `theme: <name>`，缺省用 DEFAULT。
新增主题：写一个 lib/themes/<x>.py（见 _base.py 契约），在 _REGISTRY 注册一行即可。
"""
import importlib

DEFAULT = "datasheet-editorial"

# 机器名 -> 模块路径
_REGISTRY = {
    "datasheet-editorial": "lib.themes.datasheet",
    "atelier-dark": "lib.themes.atelier",
    "technical-blueprint": "lib.themes.blueprint",
}

# 友好别名（容错：大小写/简写）
_ALIASES = {
    "datasheet": "datasheet-editorial", "editorial": "datasheet-editorial",
    "a": "datasheet-editorial",
    "atelier": "atelier-dark", "dark": "atelier-dark", "b": "atelier-dark",
    "blueprint": "technical-blueprint", "technical": "technical-blueprint",
    "c": "technical-blueprint",
}


def available():
    """返回可用主题机器名列表。"""
    return list(_REGISTRY)


def resolve_name(name):
    """把任意输入规整成已注册的机器名（找不到则回退 DEFAULT）。"""
    key = (name or "").strip().lower()
    key = _ALIASES.get(key, key)
    return key if key in _REGISTRY else DEFAULT


def get_theme(name=None):
    """返回主题模块对象；找不到/导入失败时回退到 DEFAULT。"""
    key = resolve_name(name)
    try:
        return importlib.import_module(_REGISTRY[key])
    except Exception:
        # 该主题模块缺失或报错时，不让整条管线崩，回退默认。
        if key != DEFAULT:
            return importlib.import_module(_REGISTRY[DEFAULT])
        raise
