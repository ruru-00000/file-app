import os
import shutil
import csv
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, scrolledtext

class CSVLogger:
    def __init__(self, log_path="log.csv"):
        self.log_path = log_path
        # CSVファイルがない場合はヘッダー付きで新規作成 (Excel文字化け対策でutf-8-sig)
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["日時", "ファイル名", "移動先フォルダ", "ステータス"])

    def write_log(self, filename, dest_folder, status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, mode='a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, filename, dest_folder, status])

class FileOrganizerLogic:
    def __init__(self):
        self.src_dir = "振り分け元"
        self.unclassified_dir = "未該当"
        # 判定用ルールマップ (キーワード: フォルダ名)
        self.rule_map = {
            "請求書": "請求書",
            "マニュアル": "マニュアル",
            "報告書": "報告書"
        }
        self.logger = CSVLogger()
        self.last_moved_history = []  # Undo(元に戻す)用の履歴保持
        self._ensure_directories()

    def _ensure_directories(self):
        # 必要なフォルダの自動生成
        for folder in [self.src_dir, self.unclassified_dir] + list(self.rule_map.values()):
            if not os.path.exists(folder):
                os.makedirs(folder)

    def get_target_files(self):
        if not os.path.exists(self.src_dir):
            return []
        return [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))]

    def determine_destination(self, filename):
        for keyword, folder in self.rule_map.items():
            if keyword in filename:
                return folder
        return self.unclassified_dir

    def preview_assignment(self):
        files = self.get_target_files()
        if not files:
            return "振り分け元フォルダにファイルがありません。"
        
        lines = ["【割り当てプレビュー】"]
        for f in files:
            dest = self.determine_destination(f)
            lines.append(f"  {f}  ➔  [{dest}] フォルダへ移動予定")
        return "\n".join(lines)

    def execute_organization(self):
        files = self.get_target_files()
        if not files:
            return "処理対象のファイルがありません。"

        # 【非機能要求：セキュリティ】移動先の事前重複チェック（データ上書き防止ガード）
        for f in files:
            dest_dir = self.determine_destination(f)
            dest_path = os.path.join(dest_dir, f)
            if os.path.exists(dest_path):
                raise FileExistsError(f"エラー: 移動先に同名ファイルが既に存在します。\n対象ファイル: {f} (移動先: {dest_dir})")

        self.last_moved_history = []
        success_count = 0
        lines = ["【一括移動 実行結果】"]

        for f in files:
            src_path = os.path.join(self.src_dir, f)
            dest_dir = self.determine_destination(f)
            dest_path = os.path.join(dest_dir, f)

            shutil.move(src_path, dest_path)
            self.last_moved_history.append((src_path, dest_path))
            self.logger.write_log(f, dest_dir, "成功")
            lines.append(f"  [成功] {f} ➔ {dest_dir}")
            success_count += 1

        lines.append(f"\n合計 {success_count} 件のファイルを移動しました。")
        return "\n".join(lines)

    def undo_last_execution(self):
        if not self.last_moved_history:
            return False, "元に戻す直前の移動履歴がありません。"

        # 戻し先の重複チェック
        for src_path, _ in self.last_moved_history:
            if os.path.exists(src_path):
                return False, f"エラー: 元の場所に同名ファイルが既に存在するため戻せません。\n対象: {os.path.basename(src_path)}"

        undo_count = 0
        for src_path, dest_path in self.last_moved_history:
            if os.path.exists(dest_path):
                shutil.move(dest_path, src_path)
                self.logger.write_log(os.path.basename(src_path), "振り分け元に戻す(Undo)", "成功")
                undo_count += 1

        self.last_moved_history = []  # 履歴をクリア
        return True, f"直前の処理を取り消し、{undo_count} 件のファイルを元の場所に復元しました。"


class FileOrganizerView:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.root.title("ファイル自動整理アプリ")
        self.root.geometry("620 rounded")
        self.root.geometry("620x480")
        
        # ウィジェット作成
        self._create_widgets()

    def _create_widgets(self):
        # ボタン配置用の上部フレーム
        btn_frame = tk.Frame(self.root, padx=10, pady=10)
        btn_frame.pack(fill=tk.X)

        self.btn_preview = tk.Button(btn_frame, text="① 割り当てをプレビュー", bg="#ebf8ff", fg="#2b6cb0", font=("Meiryo", 9, "bold"), relief=tk.SOLID, bd=1, padding=5, command=self.app.on_preview)
        self.btn_preview.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.btn_execute = tk.Button(btn_frame, text="② 一括移動を実行", bg="#e6fffa", fg="#319795", font=("Meiryo", 9, "bold"), relief=tk.SOLID, bd=1, padding=5, command=self.app.on_execute)
        self.btn_execute.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.btn_undo = tk.Button(btn_frame, text="↩ 直前の処理を元に戻す", bg="#edf2f7", fg="#4a5568", font=("Meiryo", 9), relief=tk.SOLID, bd=1, padding=5, command=self.app.on_undo)
        self.btn_undo.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 履歴表示エリア
        lbl = tk.Label(self.root, text="【処理履歴・ステータス表示】", font=("Meiryo", 9, "bold"))
        lbl.pack(anchor=tk.W, padx=15, pady=(10, 0))

        self.txt_history = scrolledtext.ScrolledText(self.root, font=("Consolas", 10), bg="#1a202c", fg="#edf2f7")
        self.txt_history.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)
        self.txt_history.insert(tk.END, "アプリが正常に起動しました。\n「振り分け元」フォルダに整理したいファイルを配置して各ボタンを押してください。\n")

    def display_history(self, text):
        self.txt_history.insert(tk.END, f"\n--- 実行時刻: {datetime.now().strftime('%H:%M:%S')} ---\n" + text + "\n")
        self.txt_history.see(tk.END)

    def show_error(self, message):
        messagebox.showerror("重複・エラーガード", message)

    def show_info(self, title, message):
        messagebox.showinfo(title, message)


class FileOrganizerApp:
    def __init__(self, root):
        self.logic = FileOrganizerLogic()
        self.view = FileOrganizerView(root, self)

    def on_preview(self):
        res = self.logic.preview_assignment()
        self.view.display_history(res)

    def on_execute(self):
        try:
            res = self.logic.execute_organization()
            self.view.display_history(res)
            self.view.show_info("完了", "ファイルの自動仕分けが正常に完了しました。")
        except FileExistsError as e:
            self.view.show_error(str(e))
            self.view.display_history(f"[処理中断] {str(e)}")
        except Exception as e:
            self.view.show_error(f"予期せぬエラーが発生しました:\n{str(e)}")

    def on_undo(self):
        success, msg = self.logic.undo_last_execution()
        if success:
            self.view.display_history(f"[Undo成功] {msg}")
            self.view.show_info("Undo完了", msg)
        else:
            self.view.show_error(msg)
            self.view.display_history(f"[Undo失敗] {msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FileOrganizerApp(root)
    root.mainloop()