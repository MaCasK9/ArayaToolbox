# -*- coding: utf-8 -*-
"""
一键更新所有 HTML
=================
依次重新生成：
  * card_list.html     —— 卡牌列表（generate_card_list.py）
  * deck_builder.html  —— 卡组编辑器（generate_deck_builder.py）

数据更新后，只需运行本脚本即可刷新两个页面：
    conda run -n localdb python localDB/build_all.py
"""

import generate_card_list
import generate_deck_builder


def main():
    print("=== 生成卡牌列表 ===")
    generate_card_list.main()
    print("\n=== 生成卡组编辑器 ===")
    generate_deck_builder.main()
    print("\n全部完成。")


if __name__ == "__main__":
    main()
