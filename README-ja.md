# (日本語版) Pico W CO2モニター 長期運用版

![IMG_6133](https://github.com/user-attachments/assets/501ac347-8d22-4c50-b5d5-3e9043985742)
![IMG_6136](https://github.com/user-attachments/assets/66ac1ded-a521-45ee-99ad-bb02a97fbbde)

このMicroPythonプロジェクトは、Raspberry Pi Pico Wを、堅牢で長期稼働可能なCO2・温度・湿度モニターに変えるものです。ウォッチドッグタイマー、自動再接続、メモリ管理、予防的なデイリーリブートなどの機能を組み込み、数ヶ月、あるいは数年単位での安定性を目指して設計されています。

センサーデータ（CO2、温度、湿度、THI）は4桁7セグメントディスプレイに表示され、データロギングと分析のためにMQTTブローカーに送信されます。

## 主な特徴

- **長期安定性**: 「一度設置したら忘れてしまえる」ような運用を目指した設計。
- **堅牢なエラー処理**: Wi-Fi、MQTT、センサーのエラーから自動的に復旧。
- **ウォッチドッグタイマー**: メインループがフリーズした場合にデバイスをリセット。
- **メモリ管理**: ヒープの断片化を防ぐための積極的なガベージコレクション。
- **予防的リセット**: 健全な状態を保つための毎日の再起動。
- **ローカルディスプレイ**: TM1637ディスプレイにCO2濃度と温湿度指数（THI）を表示。
- **MQTT連携**: センサーデータとシステムステータスをMQTTブローカーに送信。
- **ファイルロギング**: 重要なイベントやエラーをローカルの`system.log`ファイルに記録し、自動でローテーション。
- **設定しやすい構成**: ネットワークとMQTTの設定は、独立した`config.py`ファイルに保存。

## 必要なハードウェア

- Raspberry Pi Pico W
- **SCD4x CO2センサー**: (例: Sensirion SCD40 または SCD41)
- **TM1637 4桁7セグメントディスプレイ**
- ブレッドボードとジャンパーワイヤー

### 配線

| Pico W ピン | コンポーネント ピン | 説明       |
| :--------- | :------------ | :---------------- |
| **3V3(OUT)** | SCD4x VDD, TM1637 VCC | 電源             |
| **GND** | SCD4x GND, TM1637 GND | グラウンド            |
| **GP0 (I2C0 SDA)** | SCD4x SDA       | I2C データ          |
| **GP1 (I2C0 SCL)** | SCD4x SCL       | I2C クロック         |
| **GP2** | TM1637 CLK      | ディスプレイ クロック     |
| **GP3** | TM1637 DIO      | ディスプレイ データ I/O  |

## 必要なソフトウェアとライブラリ

- [MicroPython for Raspberry Pi Pico W](https://micropython.org/download/RPI_PICO_W/)
- 以下のMicroPythonライブラリ:
  - `scd4x.py`: Sensirion SCD4xセンサー用ドライバ。 [Github rst-sensors/scd4x](https://github.com/rst-sensors/scd4x/blob/main/scd4x.py) などで入手できます。
  - `tm1637.py`: TM1637ディスプレイ用ドライバ。 [micropython-tm1637](https://github.com/mcauser/micropython-tm1637) などで入手できます。
  - `umqtt.simple.py`: シンプルなMQTTクライアント。`upip`経由、または[micropython-lib](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)から入手できます。

## セットアップ手順

1.  **MicroPythonの書き込み**: まだ書き込んでいない場合は、最新のMicroPythonファームウェアをRaspberry Pi Pico Wに書き込みます。

2.  **ライブラリのアップロード**: 必要なライブラリファイル（`scd4x.py`, `tm1637.py`, `umqtt/simple.py`, `umqtt/robust.py`）をPico Wの`lib`ディレクトリにコピーします。

3.  **設定ファイルの作成**: Pico Wのルートディレクトリに`config.py`という名前のファイルを作成します。このファイルにネットワークとMQTTブローカーの情報を記述します。

    ```python
    # config.py
    
    WIFI_SSID = 'あなたのWIFI_SSID'
    WIFI_PASSWORD = 'あなたのWIFI_PASSWORD'
    
    MQTT_SERVER = '192.168.1.100' # あなたのMQTTブローカーのIPアドレス
    MQTT_PORT = 1883
    MQTT_CLIENT_ID = 'pico_w_co2_monitor_living_room' # このデバイスのユニークなID
    ```

4.  **メインスクリプトのアップロード**: このリポジトリの`main.py`スクリプトをPico Wのルートディレクトリにコピーします。デバイスは起動時にこのスクリプトを自動的に実行します。

5.  **電源投入**: Pico Wを電源に接続します。自動的にWi-Fiに接続し、センサーを初期化して監視を開始します。

## 動作の仕組み

### ディスプレイ

4桁ディスプレイは、2つの値を交互に表示します。
1.  **CO2濃度**: 数値で表示されます（例: `850`）。
2.  **温湿度指数 (THI)**: `HiXX`の形式で表示されます（例: `Hi72`）。THIは、暑さと湿度による不快さの指標です。

起動時、最初のセンサー値が取得されるまでは`init`と表示されます。

### MQTTトピック

デバイスは以下のMQTTトピックにデータを送信します。

-   `co2_data`: 最新のCO2測定値を含むシンプルなJSONペイロード。
    ```json
    {"co2": 850}
    ```
-   `sensor_data`: 利用可能な全てのセンサーデータを含むJSONペイロード。
    ```json
    {
      "timestamp": 1672531200,
      "device_id": "pico_w_co2_monitor_living_room",
      "co2": 850,
      "temperature": 24.5,
      "humidity": 55.2,
      "thi": 72.1
    }
    ```
-   `system_status`: 1時間ごとに発行される、システムの健全性メトリクスを含むJSONペイロード。
    ```json
    {
      "uptime": 3600,
      "memory_free": 125400,
      "successful_readings": 120,
      "successful_transmissions": 120,
      "sensor_errors": 0,
      "mqtt_errors": 0,
      "wifi_errors": 0,
      "timestamp": 1672534800,
      "device_id": "pico_w_co2_monitor_living_room"
    }
    ```

### ロギング

デバイスは、内蔵フラッシュストレージに`system.log`という名前のログファイルを保持します。このログは、常にシリアル接続をせずとも問題のデバッグに役立ちます。ログファイルは、ストレージの枯渇を防ぐため、50KBに達すると自動的にクリアされます。

## カスタマイズ

`main.py`スクリプトの先頭で、以下の動作パラメータを調整できます。
- `SENSOR_READ_INTERVAL`: センサーから読み取る頻度。
- `PUBLISH_INTERVAL`: MQTTにデータを送信する頻度。
- `WATCHDOG_TIMEOUT`: システムウォッチドッグのタイムアウト時間。
- `SYSTEM_RESET_INTERVAL`: 予防的再起動の間隔。

## 謝辞
このスクリプトおよびドキュメントは、GoogleのGeminiの支援を受けて調整・構成されました。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルをご覧ください。
