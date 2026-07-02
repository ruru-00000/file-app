import os
import shutil
import csv
import json
import re
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote  # 💡 日本語ファイル名の文字化けを直す標準パーツ

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

    def preview(self):
        files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))] if os.path.exists(self.src_dir) else []
        lines = [
            "【システム診断情報】",
            f"基準フォルダ: {BASE_DIR}",
            f"現在のファイル数: {len(files)} 件",
            "--------------------------------"
        ]
        if not files: 
            lines.append("➔ 振り分け元フォルダにファイルがありません。")
            return "\n".join(lines)
            
        lines.append("【割り当てプレビュー】")
        for f in files:
            dest_path = self.determine_destination(f)
            lines.append(f"  {f}  ➔  [{os.path.basename(dest_path)}] へ移動予定")
        return "\n".join(lines)

    def execute(self):
        files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))] if os.path.exists(self.src_dir) else []
        if not files: return "処理対象のファイルがありません。", None
        
        for f in files:
            dest_dir = self.determine_destination(f)
            if os.path.exists(os.path.join(dest_dir, f)):
                return f"エラー: 移動先に同名ファイルが既に存在します。\n対象: {f}", "重複エラー"

        self.last_moved_history = []
        lines = ["【一括移動 実行結果】"]
        for f in files:
            src = os.path.join(self.src_dir, f)
            dest_dir = self.determine_destination(f)
            dest = os.path.join(dest_dir, f)
            shutil.move(src, dest)
            self.last_moved_history.append((src, dest))
            self.write_log(f, os.path.basename(dest_dir), "成功")
            lines.append(f"  [成功] {f} ➔ {os.path.basename(dest_dir)}")
        return "\n".join(lines) + f"\n\n合計 {len(files)} 件移動しました。", "一括仕分け完了！"

    def process_uploaded_file(self, filename, file_content):
        self.last_moved_history = []
        dest_dir = self.determine_destination(filename)
        dest_path = os.path.join(dest_dir, filename)
        
        if os.path.exists(dest_path):
            return f"  [エラー] {filename} はすでに移動先に存在するためスキップしました", False

        # ファイル書き出し
        with open(dest_path, "wb") as f:
            f.write(file_content)
            
        pseudo_src = os.path.join(self.src_dir, filename)
        self.last_moved_history.append((pseudo_src, dest_path))
        self.write_log(filename, os.path.basename(dest_dir), "成功(ドロップ)")
        
        return f"  [成功] {filename} ➔ {os.path.basename(dest_dir)}", True

    def undo(self):
        if not self.last_moved_history: return "元に戻す直前の移動履歴がありません。", "Undo失敗"
        count = 0
        for src, dest in self.last_moved_history:
            if os.path.exists(dest):
                shutil.move(dest, src)
                self.write_log(os.path.basename(src), "Undo戻し", "成功")
                count += 1
        self.last_moved_history = []
        return f"[Undo成功] {count} 件のファイルを振り分け元に戻しました。", "元に戻しました！"

logic = FileOrganizerLogic()

class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open(os.path.join(BASE_DIR, 'index.html'), 'rb') as f: 
                self.wfile.write(f.read())
        elif self.path in ['/preview', '/execute', '/undo']:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            alert_msg = None
            if self.path == '/preview': res_text = logic.preview()
            elif self.path == '/execute': res_text, alert_msg = logic.execute()
            elif self.path == '/undo': res_text, alert_msg = logic.undo()
            
            response = {"result": f"--- 実行時刻: {datetime.now().strftime('%H:%M:%S')} ---\n" + res_text}
            if alert_msg: response["alert"] = alert_msg
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/drop':
            content_length = int(self.headers['Content-Length'])
            
            # 💡 修正：安全にブラウザからのファイル名を取り出してデコードする
            raw_filename = self.headers.get('X-File-Name', 'unknown_file')
            filename = unquote(raw_filename)
            
            file_content = self.rfile.read(content_length)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            log_line, success = logic.process_uploaded_file(filename, file_content)
            
            res_text = "【ドロップ仕分け 実行結果】\n" + log_line
            alert_msg = "ドロップ仕分けが完了しました！" if success else "重複エラーまたはスキップされました"
            
            response = {
                "result": f"--- 実行時刻: {datetime.now().strftime('%H:%M:%S')} ---\n" + res_text,
                "alert": alert_msg
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

if __name__ == '__main__':
    import webbrowser
    import threading

    def open_browser():
        webbrowser.open("http://localhost:8080")

    server = HTTPServer(('localhost', 8080), WebServerHandler)
    threading.Timer(0.5, open_browser).start()
    print("🚀 アプリ用サーバーが起動しました。")
    server.serve_forever()