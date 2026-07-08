import os
import shutil
import csv
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# プログラムが置かれているフォルダの絶対パスを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class FileOrganizerLogic:
    def __init__(self):
        self.src_dir = os.path.join(BASE_DIR, "振り分け元")
        self.unclassified_dir = os.path.join(BASE_DIR, "未該当")
        self.rule_map = {"実験": "実験", "数学": "数学", "英語": "英語"}
        self.log_path = os.path.join(BASE_DIR, "log.csv")
        self.last_moved_history = []
        self._ensure_directories()

    def _ensure_directories(self):
        # 必要なフォルダを作成
        for keyword, folder in self.rule_map.items():
            full_path = os.path.join(BASE_DIR, folder)
            if not os.path.exists(full_path): os.makedirs(full_path)
            
        for folder in [self.src_dir, self.unclassified_dir]:
            if not os.path.exists(folder): os.makedirs(folder)
            
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerow(["日時", "ファイル名", "移動先フォルダ", "ステータス"])

    def write_log(self, filename, dest, status):
        with open(self.log_path, mode='a', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, dest, status])

    def determine_destination(self, filename):
        for keyword, folder in self.rule_map.items():
            if re.search(keyword, filename): 
                return os.path.join(BASE_DIR, folder)
        return self.unclassified_dir

    def execute(self):
        if not os.path.exists(self.src_dir):
            return False, "振り分け元フォルダが存在しません。"
            
        files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))]
        if not files: 
            return False, "振り分け元フォルダにファイルがありません。"
        
        # 重複チェック
        for f in files:
            dest_dir = self.determine_destination(f)
            if os.path.exists(os.path.join(dest_dir, f)):
                return False, f"エラー: 移動先に同名ファイルが既に存在します。\n対象: {f}"

        self.last_moved_history = []
        count = 0
        for f in files:
            src = os.path.join(self.src_dir, f)
            dest_dir = self.determine_destination(f)
            dest = os.path.join(dest_dir, f)
            shutil.move(src, dest)
            self.last_moved_history.append((src, dest))
            self.write_log(f, os.path.basename(dest_dir), "成功")
            count += 1
            
        return True, f"{count} 件のファイルを自動整理しました！"

    def undo(self):
        if not self.last_moved_history: 
            return False, "元に戻す履歴がありません。"
            
        count = 0
        for src, dest in self.last_moved_history:
            if os.path.exists(dest):
                shutil.move(dest, src)
                self.write_log(os.path.basename(src), "Undo戻し", "成功")
                count += 1
        self.last_moved_history = []
        return True, f"{count} 件のファイルを「振り分け元」に戻しました。"


class AppUI(tk.Tk):
    def __init__(self, logic):
        super().__init__()
        self.logic = logic
        self.title("ファイル自動整理アプリ")
        self.geometry("800x500")
        
        # UIのセットアップ
        self.setup_ui()
        self.refresh_directories()

    def setup_ui(self):
        # 上部ツールバー
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED, bg="#f0f0f0")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="🔄 更新", command=self.refresh_directories).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="✨ 自動仕分けを実行", bg="#d0e8f1", command=self.execute_sort).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="↩️ 元に戻す", command=self.execute_undo).pack(side=tk.LEFT, padx=2, pady=2)

        # メインパネル（左右分割）
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左側：フォルダツリー
        left_frame = tk.Frame(paned_window)
        paned_window.add(left_frame, minsize=200)
        
        tk.Label(left_frame, text="📁 フォルダ一覧", anchor="w").pack(fill=tk.X)
        self.tree_dirs = ttk.Treeview(left_frame, show="tree")
        self.tree_dirs.pack(fill=tk.BOTH, expand=True)
        self.tree_dirs.bind("<<TreeviewSelect>>", self.on_dir_select)

        # 右側：ファイル一覧
        right_frame = tk.Frame(paned_window)
        paned_window.add(right_frame, minsize=400)
        
        self.current_folder_label = tk.Label(right_frame, text="📄 ファイル一覧", anchor="w")
        self.current_folder_label.pack(fill=tk.X)
        
        columns = ("name", "type")
        self.tree_files = ttk.Treeview(right_frame, columns=columns, show="headings")
        self.tree_files.heading("name", text="ファイル名")
        self.tree_files.heading("type", text="種類")
        self.tree_files.column("name", width=300)
        self.tree_files.column("type", width=100)
        self.tree_files.pack(fill=tk.BOTH, expand=True)

        self.current_selected_path = None

    def refresh_directories(self):
        # 左側のツリーをクリア
        for item in self.tree_dirs.get_children():
            self.tree_dirs.delete(item)
            
        # 対象となるフォルダリスト（ベースディレクトリ内のフォルダ）
        target_folders = ["振り分け元", "実験", "数学", "英語", "未該当"]
        
        root_node = self.tree_dirs.insert("", "end", text="🏠 アプリルート (Base Dir)", open=True)
        
        for folder in target_folders:
            folder_path = os.path.join(BASE_DIR, folder)
            if os.path.exists(folder_path):
                # ツリーにアイテムを追加し、パスを記憶させる
                self.tree_dirs.insert(root_node, "end", text=f"📁 {folder}", values=(folder_path,))
                
        self.refresh_files()

    def on_dir_select(self, event):
        selected = self.tree_dirs.selection()
        if not selected: return
        
        item = self.tree_dirs.item(selected[0])
        values = item.get("values")
        if values:
            self.current_selected_path = values[0]
            folder_name = os.path.basename(self.current_selected_path)
            self.current_folder_label.config(text=f"📄 ファイル一覧 - [{folder_name}]")
            self.refresh_files()
        else:
            self.current_selected_path = None
            self.current_folder_label.config(text="📄 ファイル一覧")
            self.refresh_files()

    def refresh_files(self):
        # 右側のファイル一覧をクリア
        for item in self.tree_files.get_children():
            self.tree_files.delete(item)
            
        if not self.current_selected_path or not os.path.exists(self.current_selected_path):
            return
            
        try:
            for item in os.listdir(self.current_selected_path):
                full_path = os.path.join(self.current_selected_path, item)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(item)[1] or "ファイル"
                    self.tree_files.insert("", "end", values=(item, ext))
        except Exception as e:
            print(f"読み込みエラー: {e}")

    def execute_sort(self):
        success, msg = self.logic.execute()
        if success:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showwarning("お知らせ", msg)
        self.refresh_directories()
        self.refresh_files()

    def execute_undo(self):
        success, msg = self.logic.undo()
        if success:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showwarning("お知らせ", msg)
        self.refresh_directories()
        self.refresh_files()

if __name__ == '__main__':
    # ロジックの初期化
    logic = FileOrganizerLogic()
    # アプリの起動
    app = AppUI(logic)
    app.mainloop()