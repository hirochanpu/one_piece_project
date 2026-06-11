import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import numpy as np
from itertools import product


# --- 1. 準備：住所（パス）の整理 ---
base_dir = os.path.dirname(__file__)
img_path = os.path.join(base_dir, "図13.png") 
excel_path = os.path.join(base_dir, "ONE_PIECE_DATE_FILE_ver.13.xlsx")

st.set_page_config(page_title="ONE PIECE 航海記", layout="wide")
st.title("🏴‍☠️ グランドライン航海日誌")

# --- 🔐 簡易パスワード検問所 ---
def check_password():
    """正しいパスワードが入力されたら True を返す"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.subheader("🔑 閲覧制限エリア")
    user_pass = st.text_input("パスワードを入力してください：", type="password")
    
    if user_pass:
        if user_pass == st.secrets["auth_password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ パスワードが違います！")
    return False

# パスワードが合っていなければここでプログラムを止める！
if not check_password():
    st.stop()

# --- 2. データの読み込み ---
try:
    df_log = pd.read_excel(excel_path, sheet_name="航海日誌")
    df_chars = pd.read_excel(excel_path, sheet_name="キャラクターマスタ")
    df_loc = pd.read_excel(excel_path, sheet_name="場所マスタ")

    # --- 3. データのクリーニングと合体 ---
    # 空白（ゴミ）を取り除くプロの掃除だ
    for df in [df_log, df_chars, df_loc]:
        df.columns = df.columns.str.strip()

        # 【重要】1539年を基準に、全ログの「海円暦」を確定させる
    # 「1539 - 何年前」で各通算日の年を算出
    df_log['海円暦'] = 1539 + df_log['年（何年前の出来事か）']


    # 通算日と海円暦の「完全な対応表」を作成（重複削除）
    day_to_year_map = df_log[['通算日', '海円暦']].drop_duplicates().set_index('通算日')['海円暦']

    # キャラマスタから必要な情報だけ抜く（死亡年関連をしっかりな！）
    df_chars_mini = df_chars[['登場キャラID', '名前', '誕生年（海円暦）', '死亡年（海円暦）', '生存ステータス','登場日','退場日']]
    df_loc_mini = df_loc[['場所ID', '表示名', 'X', 'Y']]

    # 日誌にキャラと場所を合体！
    df_combined = pd.merge(df_log, df_chars_mini, on='登場キャラID', how='left')
    route_data = pd.merge(df_combined, df_loc_mini, on='場所ID', how='left')

    # --- 4. 【重要】「居座り」のためのデータ穴埋め ---
    # ① 全通算日と全キャラの組み合わせを作る
    all_days = sorted(route_data['通算日'].unique())
    all_chars = route_data['登場キャラID'].unique()
    full_index = pd.DataFrame(list(product(all_days, all_chars)), columns=['通算日', '登場キャラID'])

    # ② 実際のログをぶつける
    full_map_data = pd.merge(full_index, route_data, on=['通算日', '登場キャラID'], how='left')

    # ③ 【ここがプロの技！】キャラごとに「前の日の場所」を引き継ぐ
    # これで、データがない日もキャラが最後にいた場所に留まってくれるぞ
    full_map_data['海円暦'] = full_map_data['通算日'].map(day_to_year_map)
    full_map_data = full_map_data.sort_values(['登場キャラID', '通算日'])
    info_cols = ['名前', '登場キャラ', '誕生年（海円暦）', '死亡年（海円暦）','生存ステータス','登場日', '退場日', '海円暦']
    full_map_data[info_cols] = full_map_data.groupby('登場キャラID')[info_cols].ffill().bfill()

    # ④ その後、場所（X, Y）をffillで埋める（これで「居座り」が完成する）
    full_map_data[['X', 'Y', '場所名', '表示名']] = full_map_data.groupby('登場キャラID')[['X', 'Y', '場所名', '表示名']].ffill()
    # まだ登場していない（過去にデータがない）行は消す
    full_map_data['X_jittered'] = full_map_data['X'].fillna(-9999) 
    full_map_data['Y_jittered'] = full_map_data['Y'].fillna(-9999)

# 座標が NaN（空っぽ）になった行は、Plotlyが勝手に「表示しない」として扱ってくれるぞ！

    # --- 5. 年齢と表示名の計算（享年対応） ---
    # ここで current_year ではなく、その行の「海円暦」を使って計算するんだ
    def calc_age_label(row):
        birth = row['誕生年（海円暦）']
        death = row['死亡年（海円暦）']
        curr = row['海円暦']
        name = row['登場キャラ']
        
        if pd.isna(birth) or pd.isna(curr): return name
        
        
        # 死亡判定（生存ステータスが「死亡」かつ、現在の海円暦が死亡年以降）
        if row['生存ステータス'] == '1' and not pd.isna(death) and curr >= death:
            age = int(death - birth)
            return f"{name} (享年 {age}歳)"
        else:
            age = int(curr - birth)
            return f"{name} ({age}歳)"


    full_map_data['表示用名前'] = full_map_data.apply(calc_age_label, axis=1)

    jitter_strength = 20.0
    np.random.seed(42)
    full_map_data['X_jittered'] = full_map_data['X'] 
    full_map_data['Y_jittered'] = full_map_data['Y'] + np.random.uniform(-jitter_strength, jitter_strength, len(full_map_data))


# --- 登場・退場制御の魔法 ---

    def apply_visibility(row):
        # 登場前、または退場後の場合は座標を消す
        if pd.isna(row['登場日']) or row['通算日'] < row['登場日']:
            return np.nan, np.nan
    # ② 退場日が設定されていて、かつ通算日がそれを過ぎていたら消す（物語的な離脱）
        if not pd.isna(row['退場日']) and row['通算日'] > row['退場日']:
            return np.nan, np.nan
    # ③ 【重要】死亡判定：生存ステータスが「1（死亡）」かつ、現在の年が死亡年以降なら消す
        curr_year = row['海円暦']
        death_year = row['死亡年（海円暦）']
        if str(row['生存ステータス']) == '1' and not pd.isna(death_year):
            if curr_year > death_year:
                return np.nan, np.nan
            
        return row['X_jittered'], row['Y_jittered']

    # 座標を書き換えて、期間外のキャラを「透明」にする
    full_map_data[['X_jittered', 'Y_jittered']] = full_map_data.apply(
        lambda r: pd.Series(apply_visibility(r)), axis=1
    )



    # --- 6. 仕上げ：ジッター（重なり防止）と描画 ---

    #st.write(full_map_data.head(150))
    # --- 7. Plotlyで海図を作成 ---
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img_width, img_height = img.size

        all_character_names = sorted(route_data['登場キャラ'].dropna().unique())
        full_map_data['登場キャラ'] = pd.Categorical(
            full_map_data['登場キャラ'], 
            categories=all_character_names,
            ordered=True
        )
        fig = px.scatter(
            full_map_data.sort_values('通算日'),
            x="X_jittered",
            y="Y_jittered",
            animation_frame="通算日",
            color="登場キャラ",
            animation_group="登場キャラID",
            hover_name="表示名",
            text="表示用名前",
            category_orders={"登場キャラ": all_character_names},
            range_x=[-870, 870],
            range_y=[-476.5, 476.5],
            hover_data={'海円暦': True, '出来事': True, 'X_jittered': False, 'Y_jittered': False},
            title="🏴‍☠️ グランドライン航海記（時系列アニメーション）"
        )

        fig.update_traces(marker=dict(size=6), textfont=dict(size=9),textposition='middle right',mode='markers+text')

        fig.add_layout_image(
            dict(source=img, xref="x", yref="y", x=-780, y=476.5,
                 sizex=1740, sizey=953, sizing="stretch", opacity=1.0, layer="below")
        )

        fig.update_xaxes(
            dict(range=[-870, 870], autorange=False, 
                 showgrid=False, zeroline=False, visible=False)
        )
        fig.update_yaxes(
            dict(range=[-476.5, 476.5], autorange=False, 
                 showgrid=False, zeroline=False, visible=False)
        )
        fig.update_layout(width=1200, height=675, margin=dict(l=0, r=0, t=0, b=0))

        # --- アニメーション速度の設定（ここを変えろ！） ---


        duration = 2500  # 1コマが切り替わる時間（ミリ秒）。数字を大きくすると遅くなるぞ。
        redraw_time = 5000 # 描画にかける時間。durationより小さくするのがコツだ。


        fig.update_layout(
            updatemenus=[{
                "buttons": [
                    {
                        "args": [None, {"frame": {"duration": duration, "redraw": True}, "fromcurrent": True}],
                        "method": "animate"
                    },
                    {
                        "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}],
                        "method": "animate"
                    }
                ]
            }]
        )
    # --- 8. 懸賞金データの読み込みと加工 ---
        try:
            # シート名は「懸賞金・肩書ログ」だったな！
            df_bounty_log = pd.read_excel(excel_path, sheet_name="懸賞金・肩書ログ")
            df_bounty_log.columns = df_bounty_log.columns.str.strip()
            
            # データの掃除（通算日の型合わせとIDのクレンジング）
            df_bounty_log['通算日'] = pd.to_numeric(df_bounty_log['通算日'], errors='coerce')
            df_bounty_log['登場キャラID'] = df_bounty_log['登場キャラID'].astype(str).str.strip()


            # 土台（全日程×全キャラ）に懸賞金データをぶつける
            bounty_data = pd.merge(full_index, df_bounty_log, on=['通算日', '登場キャラID'], how='left')

            # 名前をマスタから結合
            bounty_data = pd.merge(bounty_data, df_chars[['登場キャラID', '名前']], on='登場キャラID', how='left')
            found_data_count = bounty_data['懸賞金'].count()
            #st.write(f"DEBUG: マージ後の有効なデータ件数 = {found_data_count}")

            # 【プロの技】懸賞金の穴埋め（ffill）
            # これで「賞金が更新された日」以外の空欄が、最新の金額で埋まるんだ
            #bounty_data = bounty_data.sort_values(['登場キャラID', '通算日'])
            bounty_data['懸賞金'] = bounty_data.groupby('登場キャラID')['懸賞金'].ffill().fillna(0)
            bounty_data['肩書'] = bounty_data.groupby('登場キャラID')['肩書'].ffill().fillna("海賊")

            # 2. 【ここがキモだ！】懸賞金が0より大きいデータだけを抽出する
            # これで、手配前のキャラはグラフの枠外に追い出されるぞ
            bounty_data['ランキング用ラベル'] = bounty_data['名前'] + " [" + bounty_data['肩書'] + "]"

            # 地図と同じく、登場前・退場後のキャラは賞金ランキングからも外す（任意だぞ！）
            # ここでは「その日に地図にいる（X_jitteredがNaNじゃない）奴」だけを対象にする
            valid_ids = full_map_data.dropna(subset=['X_jittered'])[['通算日', '登場キャラID']]
            bounty_plot_df = pd.merge(valid_ids, bounty_data, on=['通算日', '登場キャラID'], how='inner')
            bounty_plot_df = bounty_plot_df[bounty_plot_df['懸賞金'] > 0]
            #st.write(bounty_plot_df)
        
        except Exception as e:
            st.warning(f"懸賞金ログの読み込みでエラーだ：{e}")
            bounty_plot_df = pd.DataFrame()

            #--- 10. 勢力・所属データの処理 ---
        try:
            df_factions = pd.read_excel(excel_path, sheet_name="勢力マスタ")
            df_affil = pd.read_excel(excel_path, sheet_name="所属ログ")
            
            # クリーニング（プロの基本だ！）
            df_factions.columns = df_factions.columns.str.strip()
            df_affil.columns = df_affil.columns.str.strip()
            df_affil['登場キャラID'] = df_affil['登場キャラID'].astype(str).str.strip()
            #df_affil['通算日'] = pd.to_numeric(df_affil['通算日'], errors='coerce')
            if '名前' in df_affil.columns:
                df_affil = df_affil.drop(columns=['名前'])

            # 土台とマージして、所属を「居座り（ffill）」させる
            affil_data = pd.merge(full_index, df_affil, on=['通算日', '登場キャラID'], how='left')
            affil_data = affil_data.sort_values(['登場キャラID', '通算日'])
            #affil_data['勢力ID'] = affil_data.groupby('登場キャラID')['勢力ID'].ffill()
            # これで、ログがない行にも「キャラIDに対応する名前」の器ができる
            faction_final = pd.merge(
                affil_data, 
                df_chars[['登場キャラID', '名前', '誕生年（海円暦）', '生存ステータス', '死亡年（海円暦）','登場日', '退場日']], 
                on='登場キャラID', 
                how='left'
            )



            # 3. 【プロの技】名前と勢力IDをまとめて「居座り（ffill）」させる
            # 名前も居座りさせることで、全日程で名前が空欄になるのを防ぐぞ
            cols_to_fill = ['名前', '勢力ID']
            if '役職' in faction_final.columns:
                cols_to_fill.append('役職')
            faction_final[cols_to_fill] = faction_final.groupby('登場キャラID')[cols_to_fill].ffill().bfill()

            # 名前、年齢、勢力名を合体！
            #faction_final = pd.merge(affil_data, df_chars[['登場キャラID', '名前', '誕生年（海円暦）', '生存ステータス', '死亡年（海円暦）']], on='登場キャラID', how='left')
            faction_final = pd.merge(faction_final, df_factions[['勢力ID', '勢力名']], on='勢力ID', how='left')
            #st.write("最終的な表示データの件数:", len(bounty_plot_df))
            # 海円暦をマッピング（main_3.pyのday_to_year_mapを使うぞ）
            faction_final['海円暦'] = faction_final['通算日'].map(day_to_year_map)



            #st.dataframe(faction_final.head(200))
        except Exception as e:
            st.warning(f"勢力データの読み込みに失敗したぞ：{e}")

        # --- 11. 技データの読み込みと加工 ---
        try:
            df_skills = pd.read_excel(excel_path, sheet_name="技マスタ")
            df_skills.columns = df_skills.columns.str.strip()
            
            # 決め技カウントが 0 より大きいものだけを抽出し、多い順に並べる
            df_finisher = df_skills[df_skills['決め技カウント'] > 0].copy()
            df_finisher = df_finisher.sort_values('決め技カウント', ascending=False)
            
            # グラフ用のラベル作成（「ゴムゴムの銃 (ルフィ)」みたいにするぞ）
            df_finisher['技表示名'] = df_finisher['技名'] + " (" + df_finisher['使用者'] + ")"
        except Exception as e:
            st.error(f"技マスタの読み込みに失敗したぞ：{e}")

        # --- 9. タブで表示を切り替える（プロのUI） ---
        tab_map, tab_rank, tab_faction = st.tabs(["🗺️ 航海マップ", "💰 ランキング", "🏴‍☠️ 勢力詳細"])
        
        with tab_map:
            # 元々の地図を表示
            st.plotly_chart(fig, use_container_width=True)
            #st.dataframe(route_data[['通算日', '話数', '登場キャラ', '場所名', '出来事']])

        with tab_rank:
            st.subheader("💰 時代別・懸賞金ランキング")
            
            # 1. ユーザーが選んだ日（target_day）を取得
            # 地図のスライダーと key を変えるか、同じにして連動させるかは自由だ！
            target_day = st.select_slider("確認したい通算日を選択", options=all_days, key="bounty_slider_final")

            # 2. 【ここが最重要】「その日以前」のログをすべて取得する
            # これで過去の懸賞金データもすべてカゴに入るぞ
            past_logs = df_bounty_log[df_bounty_log['通算日'] <= target_day].copy()

            if not past_logs.empty:
                # 3. キャラごとに「最新（一番大きい通算日）」のデータだけを抽出
                # これで、ルフィの賞金が上がっても「最新の額」1つだけが残る
                latest_bounties = past_logs.sort_values(['登場キャラID', '通算日']).groupby('登場キャラID').last().reset_index()

                # 4. キャラクターマスタと合体して「名前」や「生死」を紐づける
                # 重複エラーを防ぐためにマスタ側も念のため掃除しておくぞ
                clean_chars = df_chars.drop_duplicates(subset=['登場キャラID'])
                ranking_df = pd.merge(latest_bounties, clean_chars, on='登場キャラID', how='left').reset_index(drop=True)

                # 5. 生死フィルター（死んだ奴は消去！）
                current_year = day_to_year_map.get(target_day, 1539)
                ranking_df['生存ステータス'] = ranking_df['生存ステータス'].astype(str)
                # 「死亡ステータスが1」かつ「今の年が死亡年を過ぎている」奴を除外
                ranking_df = ranking_df[~((ranking_df['生存ステータス'] == '1') & (current_year > ranking_df['死亡年（海円暦）']))]

                # 6. 数値クレンジング
                ranking_df['懸賞金'] = pd.to_numeric(ranking_df['懸賞金'], errors='coerce').fillna(0)
                ranking_df = ranking_df[ranking_df['懸賞金'] > 0].sort_values('懸賞金', ascending=False)

                if not ranking_df.empty:
                    fig_bounty = px.bar(
                        ranking_df.head(15), 
                        x='懸賞金', y='名前', orientation='h',
                        title=f"第 {target_day} 日（海円暦{int(current_year)}年）時点の懸賞金",
                        color='懸賞金', color_continuous_scale='YlOrRd', text='懸賞金'
                    )
                    fig_bounty.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_bounty, use_container_width=True)
                else:
                    st.info(f"第 {target_day} 日時点では、まだ誰も懸賞金がかかってねェようだ！")
            else:
                st.info("データが空だぞ！")

        # --- タブへの表示 ---
        with tab_rank:
            st.divider() # 懸賞金グラフとの区切り線だ
            st.subheader("🔥 決め技ランキング")
            
            if not df_finisher.empty:
                # グラフ作成
                fig_skill = px.bar(
                    df_finisher.head(15),  # 上位15位くらいが見やすいぞ
                    x='決め技カウント',
                    y='技表示名',
                    orientation='h',
                    title="トドメを刺した回数 TOP15",
                    color='決め技カウント',
                    color_continuous_scale='Reds', # 決め技っぽく情熱の赤だ！
                    text='決め技カウント'
                )
                
                fig_skill.update_layout(
                    height=600,
                    yaxis={'categoryorder':'total ascending'}, # カウント順に並べる
                    xaxis_title="決め技回数",
                    yaxis_title="技名 (使用者)"
                )
                
                st.plotly_chart(fig_skill, use_container_width=True)
            else:
                st.info("決め技データがまだ登録されていないようだ。マスタを更新してみてくれ！")

        # --- タブへの表示 ---
        with tab_rank:
            st.divider() # 懸賞金グラフとの区切り線だ
            st.subheader("⚔️ 技使用頻度ランキング")
            
            if not df_finisher.empty:
                # グラフ作成
                fig_skill = px.bar(
                    df_finisher.head(15),  # 上位15位くらいが見やすいぞ
                    x='使用回数',
                    y='技表示名',
                    orientation='h',
                    title="技使用頻度 TOP15",
                    color='使用回数',
                    color_continuous_scale='Greens', # 決め技っぽく情熱の赤だ！
                    text='使用回数'
                )
                
                fig_skill.update_layout(
                    height=600,
                    yaxis={'categoryorder':'total ascending'}, # カウント順に並べる
                    xaxis_title="使用回数",
                    yaxis_title="技名 (使用者)"
                )
                
                st.plotly_chart(fig_skill, use_container_width=True)
            else:
                st.info("決め技データがまだ登録されていないようだ。マスタを更新してみてくれ！")


        with tab_faction:
            st.subheader("🏴‍☠️ 勢力別名簿 ＆ キャラクター歴史比較")
            
            # 1. ユーザーが「今、いつの名簿を見たいか」を選ぶ（お前さんの元のスライダー！）
            target_day_fac = st.select_slider("確認したい通算日を選択", options=all_days, key="faction_slider_unique")
            
            # その日のベースデータを抽出
            current_roster = faction_final[faction_final['通算日'] == target_day_fac].copy()
            
            # 2. 登場前・退場後・死亡済みのキャラを排除する検問所（お前さんの元のロジック！）
            def is_visible_roster(row):
                day = row['通算日']
                entry = row['登場日']
                exit = row['退場日']
                curr_year = row['海円暦']
                death_year = row['死亡年（海円暦）']
                status = str(row['生存ステータス'])

                if pd.notna(entry) and day < entry:
                    return False
                if pd.notna(exit) and day > exit:
                    return False
                if status == '1' and pd.notna(death_year) and curr_year > death_year:
                    return False
                
                return True

            # フィルター実行！
            current_roster = current_roster[current_roster.apply(is_visible_roster, axis=1)]
            
            # 3. 年齢計算（故人対応版・お前さんの元のロジック！）
            def get_age_display(row):
                birth = row['誕生年（海円暦）']
                death = row['死亡年（海円暦）']
                curr = row['海円暦']
                if pd.isna(birth) or pd.isna(curr): return "不明"
                if str(row['生存ステータス']) == '1' and not pd.isna(death) and curr >= death:
                    return f"{int(death - birth)}歳 (故人)"
                return f"{int(curr - birth)}歳"
            
            current_roster['年齢'] = current_roster.apply(get_age_display, axis=1)
            
            # 有効なデータがあるかチェックして処理を開始
            if not current_roster.empty:
                # 画面を綺麗に2分割（左側に勢力セレクト、右側にキャラ追加のマルチセレクト）
                col_sel1, col_sel2 = st.columns(2)
                
                with col_sel1:
                    # ① 勢力選択セレクトボックス
                    roster_with_faction = current_roster.dropna(subset=['勢力名'])
                    available_factions = sorted(roster_with_faction['勢力名'].unique().tolist())
                    selected_faction = st.selectbox("ベースとなる勢力を選択：", available_factions)
                
                with col_sel2:
                    # ② 同時に比較したいキャラをポチポチ選べるマルチセレクト
                    all_available_chars = sorted(current_roster['名前'].dropna().unique().tolist())
                    selected_extra_chars = st.multiselect("同時に比較・追跡したいキャラを個別追加：", all_available_chars)

                # 【丁寧なデータ抽出と足し算】
                df_faction_part = current_roster[current_roster['勢力名'] == selected_faction].copy()
                df_extra_part = current_roster[current_roster['名前'].isin(selected_extra_chars)].copy()
                combined_roster = pd.concat([df_faction_part, df_extra_part]).drop_duplicates(subset=['登場キャラID'])

                # 地図データから、その日の「場所名」と「出来事」の列を合流
                day_map_info = full_map_data[full_map_data['通算日'] == target_day_fac][['登場キャラID', '場所名', '出来事']]
                combined_roster = pd.merge(combined_roster, day_map_info, on='登場キャラID', how='left')

                # 【表示する列の組み立て】
                display_cols = ['勢力名', '名前', '年齢', '場所名', '出来事']
                
                # 所属ログから拾うようにした『役職』列がデータ内に存在していれば、列を挟み込む！
                if '役職' in combined_roster.columns:
                    display_cols.insert(2, '役職')

                display_df = combined_roster[display_cols].copy()
                
                # 空欄（NaN）を文字で埋める処理
                display_df['勢力名'] = display_df['勢力名'].fillna("無所属・その他")
                display_df['場所名'] = display_df['場所名'].fillna("移動中または不明")
                display_df['出来事'] = display_df['出来事'].fillna("（特にログなし）")

                # テーブルで一覧を表示
                st.markdown(f"### 📅 第 {target_day_fac} 日時点の動向一覧")
                st.table(display_df.sort_values('勢力名'))

                st.markdown("---")

                # 🔍 キャラクター詳細ビュアー（お前さんの技データ連携を完全尊重版！）
                st.markdown("#### 🔍 キャラクター詳細ビュアー")
                
                char_names = combined_roster['名前'].tolist()
                selected_char_name = st.selectbox("詳細を見たいキャラを選択：", ["（選択してください）"] + char_names)

                if selected_char_name != "（選択してください）":
                    char_info = combined_roster[combined_roster['名前'] == selected_char_name].iloc[0]
                    selected_cid = char_info['登場キャラID']

                    with st.container(border=True):
                        st.subheader(f"🏴‍☠️ {selected_char_name} の詳細ステータス")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**【役職・肩書】** {char_info.get('役職', 'なし')}")
                            st.write(f"**【年齢】** {char_info['年齢']}")
                            
                            # 出身地は元のキャラクターマスタから引っ張る
                            char_master = df_chars[df_chars['登場キャラID'] == selected_cid]
                            origin_place = char_master.iloc[0]['出身島・国'] if not char_master.empty and '出身島・国' in df_chars.columns else "不明"
                            st.write(f"**【出身地】** {origin_place}")
                        
                        with col2:
                            loc_name = char_info.get('場所名', '移動中または不明')
                            st.write(f"**【現在位置】** 🗺️ {loc_name}")

                            # 懸賞金データの表示
                            if 'bounty_plot_df' in locals() and not bounty_plot_df.empty:
                                char_bounty = bounty_plot_df[(bounty_plot_df['登場キャラID'] == selected_cid) & (bounty_plot_df['通算日'] == target_day_fac)]
                                if not char_bounty.empty:
                                    b_val = char_bounty.iloc[0]['懸賞金']
                                    st.write(f"**【現在の懸賞金】** 🪙 {int(b_val):,} ベリー")
                                else:
                                    st.write("**【現在の懸賞金】** 手配書なし (0ベリー)")
                            else:
                                st.write("**【現在の懸賞金】** 手配書なし")

                        st.markdown("---")
                        st.markdown("**【🔥 これまでに使った技の一覧】**")
                        
                        # 🕵️ 【ここがお前さんの設計の完全な復活とリスペクトだ！】
                        # お前さんが267行目以降で綺麗に作った『df_finisher』を使い、
                        # 使用者（名前）が完全に一致する技データを綺麗に抽出するぞ！
                        if 'df_finisher' in locals() and not df_skills.empty:
                            char_skills_df = df_skills[df_skills['使用者'] == selected_char_name]

                            if '通算日' in char_skills_df.columns:
                                char_skills_df = char_skills_df[char_skills_df['通算日'] <= target_day_fac]

                            
                            if not char_skills_df.empty:
                                for _, s_row in char_skills_df.iterrows():
                                    st.write(f"・ **{s_row['技名']}** ")
                            else:
                                st.caption(" まだこのキャラの決め技データはマスタに登録されていねェようだ！")
                        else:
                            st.caption(" 技マスタのデータが読み込まれていません。")
                            
            else:
                st.info(f"第 {target_day_fac} 日時点では、表示できるメンバーはいねェようだ！")
except Exception as e:
    st.error(f"エラーが発生したぞ！：{e}")
