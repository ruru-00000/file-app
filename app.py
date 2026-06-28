import os
import shutil
import csv
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ロジック・CSV管理クラス
class FileOrganizerLogic:
    def __init__(self):
        self.src_dir = "振り分け元"
        self.unclassified_dir = "未該当"
        self.rule_map = {"請求書": "請求書", "マニュアル": "マニュアル", "報告書": "報告書"}
        self.log_path = "log.csv"
        self.last_moved_history = []
        self._ensure_directories()

    def _ensure_directories(self):
        for folder in [self.src_dir, self.unclassified_dir] + list(self.rule_map.values()):
            if not os.path.exists(folder): os.makedirs(folder)
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerow(["日時", "ファイル名", "移動先フォルダ", "ステータス"])

    def write_log(self, filename, dest, status):
        with open(self.log_path, mode='a', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, dest, status])

    def determine_destination(self, filename):
        for keyword, folder in self.rule_map.items():
            if keyword in filename: return folder
        return self.unclassified_dir

    def preview(self):
        files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))] if os.path.exists(self.src_dir) else []
        if not files: return "振り分け元フォルダにファイルがありません。"
        lines = ["【割り当てプレビュー】"]
        for f in files:
            lines.append(f"  {f}  ➔  [{self.determine_destination(f)}] フォルダへ移動予定")
        return "\n".join(lines)

    def execute(self):
        files = [f for f in os.listdir(self.src_dir) if os.path.isfile(os.path.join(self.src_dir, f))] if os.path.exists(self.src_dir) else []
        if not files: return "処理対象のファイルがありません。", None
        
        for f in files:
            if os.path.exists(os.path.join(self.determine_destination(f), f)):
                return f"エラー: 移動先に同名ファイルが既に存在します。\n対象: {f}", "重複エラーが発生しました"

        self.last_moved_history = []
        lines = ["【一括移動 実行結果】"]
        for f in files:
            src, dest_dir = os.path.join(self.src_dir, f), self.determine_destination(f)
            dest = os.path.join(dest_dir, f)
            shutil.move(src, dest)
            self.last_moved_history.append((src, dest))
            self.write_log(f, dest_dir, "成功")
            lines.append(f"  [成功] {f} ➔ {dest_dir}")
        return "\n".join(lines) + f"\n\n合計 {len(files)} 件移動しました。", "ファイル自動仕分けが完了しました！"

    # ドロップされたファイルだけをピンポイントで仕分ける新しい機能
    def execute_drop(self, filenames):
        if not filenames: return "処理されたファイルがありません。", None

        # 重複ガードチェック
        for f in filenames:
            dest_dir = self.determine_destination(f)
            # 振り分け元にあるか、またはカレントディレクトリにあるか確認
            src_path = os.path.join(self.src_dir, f) if os.path.exists(os.path.join(self.src_dir, f)) else f
            if not os.path.exists(src_path):
                continue
            if os.path.exists(os.path.join(dest_dir, f)):
                return f"エラー: 移動先に同名ファイルが既に存在します。\n対象: {f}", "重複エラーが発生しました"

        self.last_moved_history = []
        lines = ["【ドロップ仕分け 実行結果】"]
        success_count = 0

        for f in filenames:
            # 振り分け元フォルダ、またはアプリと同じ階層にある対象ファイルを探す
            src = os.path.join(self.src_dir, f) if os.path.exists(os.path.join(self.src_dir, f)) else f
            if not os.path.exists(src):
                lines.append(f"  [スキップ] {f} (ファイルが指定フォルダに見つかりません)")
                continue

            dest_dir = self.determine_destination(f)
            dest = os.path.join(dest_dir, f)
            shutil.move(src, dest)
            self.last_moved_history.append((src, dest))
            self.write_log(f, dest_dir, "成功(ドロップ)")
            lines.append(f"  [成功] {f} ➔ {dest_dir}")
            success_count += 1

        return "\n".join(lines) + f"\n\n合計 {success_count} 件のドロップファイルを移動しました。", "ドロップ仕分けが完了しました！"

    def undo(self):
        if not self.last_moved_history: return "元に戻す直前の移動履歴がありません。", "Undo失敗"
        for src, _ in self.last_moved_history:
            if os.path.exists(src): return f"エラー: 元の場所に同名ファイルがあるため戻せません。\n対象: {os.path.basename(src)}", "Undo失敗"
        
        count = 0
        for src, dest in self.last_moved_history:
            if os.path.exists(dest):
                shutil.move(dest, src)
                self.write_log(os.path.basename(src), "Undo戻し", "成功")
                count += 1
        self.last_moved_history = []
        return f"[Undo成功] 直前の処理を取り消し、{count} 件のファイルを元に戻しました。", "元に戻しました！"

logic = FileOrganizerLogic()

# Webサーバーの挙動定義クラス
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('index.html', 'rb') as f: self.wfile.write(f.read())
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
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            filenames = data.get('filenames', [])

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            res_text, alert_msg = logic.execute_drop(filenames)
            response = {"result": f"--- 実行時刻: {datetime.now().strftime('%H:%M:%S')} ---\n" + res_text}
            if alert_msg: response["alert"] = alert_msg
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

if __name__ == '__main__':
    import webbrowser
    import threading

    def open_browser():
        webbrowser.open("http://localhost:8080")

    server = HTTPServer(('localhost', 8080), WebServerHandler)
    
    # サーバー起動1秒後に自動でブラウザを開く
    threading.Timer(1.0, open_browser).start()
    
    print("🚀 アプリ用サーバーが起動しました。")
    server.serve_forever()