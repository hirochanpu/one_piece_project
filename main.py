import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import numpy as np
from itertools import product
import time

# タイム計測用
def timer(label):
    start = time.perf_counter()
    def end():
        elapsed = time.perf_counter() - start
        print(f"[TIMER] {label}: {elapsed:.3f}秒")
    return end    

# --- 1. 準備：住所（パス）の整理 ---
base_dir = os.path.dirname(__file__)
img_path = os.path.join(base_dir, "世界地図.png") 
excel_path = os.path.join(base_dir, "ONE_PIECE_DATE_FILE.xlsx")

st.set_page_config(page_title="ONE PIECE 航海記", layout="wide")
st.title("🏴‍☠️ グランドライン航海日誌")

# =========================================================
# 📖 ここから：サイトの取扱説明書（弟子への伝授スペース）
# =========================================================
with st.expander("ℹ️ 【取扱説明書】このサイトの遊び方（クリックで開閉します！）", expanded=False):
    st.markdown("""
    ### ⚓ 概要
    このサイトは、漫画『ONE PIECE』の膨大な航海データをベースに、ルフィたちの旅路や時代の変化をリアルタイムに可視化する**「デジタル航海日誌」**を目指しています！
            ※現在は単行本13巻までの情報を整理しています。
    
    ### 🧭 基本的な使い方
    1. **画面最上部のスライダーを動かす**
       - スライダーを動かすと、その「通算日（ルフィの出航を1とする）」や「単行本巻数」の時点へタイムスリップできます。
        ※描写のないキャラなど一部推測も含まれています。ミスがあればご指摘いただけたら幸いです。
       - すべてのタブのデータが、選んだ日に合わせて一斉に連動する仕組みです！
    
    2. **3つのタブを切り替えて楽しむ**
       - **🗺️ リアルタイム海図**：その日、誰がグランドラインのどこにいたのかが地図上にプロットされる。キャラにマウスを当てると当時の年齢や出来事が見れます。
            （場所には仕様上多少の誤差があります）
       - **💰 懸賞金・技ランキング**：その巻数時点で「誰が一番懸賞金が高かったか」「どの勢力が一番危険か」がグラフで確認できます。
       - **🏴‍☠️ 勢力動向**：「麦わらの一味」などを選べば、メンバーが徐々に集まっていく歴史を連続で追えます。
            　また、勢力内のキャラの詳細データや、選択した勢力と比較したい対象も選べます。
    
       - **💡 懸賞金は基本的に登場したタイミングで登場していますが、過去回想などで推測している部分もあります。
    """)
# =========================================================
# 📖 ここまで：説明書スペース
# =========================================================


# （この下に、 timer("全データロード") などの既存の処理が続く...）
@st.cache_data
def load_excel_sheet(path, sheet_name):
    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = df.columns.str.strip()
    return df

# --- 📱 スマホ表示 & 固定ヘッダーのためのCSS魔法 ---
    st.markdown("""
    <style>
    @media (max-width: 640px) {
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        div[data-testid="column"] {
            width: 100% !important;
            margin-bottom: 15px;
        }
    }
    button[data-baseweb="tab"] {
        font-size: 14px !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
    }
    .sticky-header {
        position: -webkit-sticky;
        position: sticky;
        top: 2.875rem; 
        z-index: 999;  
        background-color: white; 
        padding-bottom: 10px;
        border-bottom: 2px solid #f0f2f6; 
    }
    </style>
""", unsafe_allow_html=True)


# =========================================================
# 🏎️ データ処理をキャッシュ化して爆速にするぞ！
# =========================================================
@st.cache_data
def load_and_process_all_data(file_path):
    df_log = load_excel_sheet(file_path, "航海日誌")
    df_chars = load_excel_sheet(file_path, "キャラクターマスタ")
    df_loc = load_excel_sheet(file_path, "場所マスタ")

    df_log['海円暦'] = 1539 + df_log['年（何年前の出来事か）']
    day_to_year_map = df_log[['通算日', '海円暦']].drop_duplicates().set_index('通算日')['海円暦']

    # 💡 【追加の仕掛け】通算日と「巻数」の紐づけマップを作成
    # ※ もしExcelの列名が「巻」や「単行本」なら、ここの '巻数' をその名前に書き換えてくれ！
    day_to_vol_map = {}
    if '巻数' in df_log.columns:
        # 通算日ごとに、最初に見つかった巻数をセットする
        day_to_vol_map = df_log.dropna(subset=['巻数']).drop_duplicates(subset=['通算日']).set_index('通算日')['巻数'].to_dict()

    df_chars_mini = df_chars[['登場キャラID', '名前', '誕生年（海円暦）', '死亡年（海円暦）', '生存ステータス','登場日','退場日']]
    df_loc_mini = df_loc[['場所ID', '表示名', 'X', 'Y']]

    df_combined = pd.merge(df_log, df_chars_mini, on='登場キャラID', how='left')
    route_data = pd.merge(df_combined, df_loc_mini, on='場所ID', how='left')

    # --- 4. 「居座り」のためのデータ穴埋め ---
    all_days = sorted(route_data['通算日'].unique())
    all_chars = route_data['登場キャラID'].unique()
    full_index = pd.DataFrame(list(product(all_days, all_chars)), columns=['通算日', '登場キャラID'])

    full_map_data = pd.merge(full_index, route_data, on=['通算日', '登場キャラID'], how='left')
    full_map_data['海円暦'] = full_map_data['通算日'].map(day_to_year_map)
    full_map_data = full_map_data.sort_values(['登場キャラID', '通算日'])
    
    info_cols = ['名前', '登場キャラ', '誕生年（海円暦）', '死亡年（海円暦）','生存ステータス','登場日', '退場日', '海円暦']
    full_map_data[info_cols] = full_map_data.groupby('登場キャラID')[info_cols].ffill().bfill()
    full_map_data[['X', 'Y', '場所名', '表示名']] = full_map_data.groupby('登場キャラID')[['X', 'Y', '場所名', '表示名']].ffill()

    # --- 5. 年齢と表示名の計算（享年対応） ---
    def calc_age_label(row):
        birth = row['誕生年（海円暦）']
        death = row['死亡年（海円暦）']
        curr = row['海円暦']
        name = row['登場キャラ']
        if pd.isna(birth) or pd.isna(curr): return name
        if row['生存ステータス'] == '1' and not pd.isna(death) and curr >= death:
            return f"{name} (享年 {int(death - birth)}歳)"
        else:
            return f"{name} ({int(curr - birth)}歳)"

    full_map_data['表示用名前'] = full_map_data.apply(calc_age_label, axis=1)

    # ジッター処理
    jitter_strength = 20.0
    np.random.seed(42)
    full_map_data['X_jittered'] = full_map_data['X'] 
    full_map_data['Y_jittered'] = full_map_data['Y'] + np.random.uniform(-jitter_strength, jitter_strength, len(full_map_data))

    def apply_visibility(row):
        if pd.isna(row['登場日']) or row['通算日'] < row['登場日']: return np.nan, np.nan
        if not pd.isna(row['退場日']) and row['通算日'] > row['退場日']: return np.nan, np.nan
        if str(row['生存ステータス']) == '1' and not pd.isna(row['死亡年（海円暦）']) and row['海円暦'] > row['死亡年（海円暦）']:
            return np.nan, np.nan
        return row['X_jittered'], row['Y_jittered']

    full_map_data[['X_jittered', 'Y_jittered']] = full_map_data.apply(lambda r: pd.Series(apply_visibility(r)), axis=1)

    # --- 8. 懸賞金データの読み込みと加工 ---
    try:
        df_bounty_log = load_excel_sheet(file_path, "懸賞金・肩書ログ")
        df_bounty_log['通算日'] = pd.to_numeric(df_bounty_log['通算日'], errors='coerce')
        df_bounty_log['登場キャラID'] = df_bounty_log['登場キャラID'].astype(str).str.strip()
    except:
        df_bounty_log = pd.DataFrame()

    #--- 10. 勢力・所属データの処理 ---
    try:
        df_factions = load_excel_sheet(file_path, "勢力マスタ")
        df_affil = load_excel_sheet(file_path, "所属ログ")
        df_affil['登場キャラID'] = df_affil['登場キャラID'].astype(str).str.strip()
        if '名前' in df_affil.columns: df_affil = df_affil.drop(columns=['名前'])
        faction_final = pd.merge(
            pd.merge(full_index, df_affil, on=['通算日', '登場キャラID'], how='left').sort_values(['登場キャラID', '通算日']), 
            df_chars[['登場キャラID', '名前', '誕生年（海円暦）', '生存ステータス', '死亡年（海円暦）','登場日', '退場日']], 
            on='登場キャラID', how='left'
        )
        cols_to_fill = ['名前', '勢力ID']
        if '役職' in faction_final.columns: cols_to_fill.append('役職')
        faction_final[cols_to_fill] = faction_final.groupby('登場キャラID')[cols_to_fill].ffill().bfill()
        faction_final = pd.merge(faction_final, df_factions[['勢力ID', '勢力名']], on='勢力ID', how='left')
        faction_final['海円暦'] = faction_final['通算日'].map(day_to_year_map)
    except:
        df_factions = pd.DataFrame()
        df_affil = pd.DataFrame()
        faction_final = pd.DataFrame()

    # --- 11. 技データの読み込み ---
    try:
        df_skills = load_excel_sheet(file_path, "技マスタ")
        df_finisher = df_skills[df_skills['決め技カウント'] > 0].copy().sort_values('決め技カウント', ascending=False)
        df_finisher['技表示名'] = df_finisher['技名'] + " (" + df_finisher['使用者'] + ")"
    except:
        df_skills = pd.DataFrame()
        df_finisher = pd.DataFrame()

    return (df_log, df_chars, df_loc, df_bounty_log, df_affil, df_skills, 
            route_data, full_map_data, faction_final, df_finisher, all_days, day_to_year_map, df_factions, day_to_vol_map)


# =========================================================
# 🧭 メイン画面描画処理
# =========================================================
try:
    end_timer = timer("全データロード")
    (df_log, df_chars, df_loc, df_bounty_log, df_affil, df_skills, 
     route_data, full_map_data, faction_final, df_finisher, all_days, day_to_year_map, df_factions, day_to_vol_map) = load_and_process_all_data(excel_path)
    end_timer()

    # 📌 共通スライダーを画面上部に固定
    #st.markdown('<div class="sticky-header">', unsafe_allow_html=True)
    
    # 💡 【大改造の肝】スライダーの表示用フォーマット関数
    def format_day_with_volume(day):
        vol = day_to_vol_map.get(day)
        if vol is not None and pd.notna(vol):
            # 巻数が数字や文字列で入っている場合、「第〇日 (単行本〇巻)」と綺麗にする
            # 過去の回想などで巻数がない場合は自動で「第〇日」の表記になるぜ！
            return f"第 {day} 日 (単行本 {vol} 巻)"
        return f"第 {day} 日"

    # スライダーに format_func を適用して、中身の数字を見やすく変身させる！
    target_day = st.select_slider(
        "⚓ 航海日誌の『通算日』を選択してくれ（全タブ共通だぞ！）", 
        options=all_days, 
        format_func=format_day_with_volume,
        key="shared_voyage_slider"
    )
    #st.markdown('</div>', unsafe_allow_html=True)

    # --- タブの作成 ---
    tab_map, tab_rank, tab_faction = st.tabs(["🗺️ リアルタイム海図", "💰 懸賞金・技ランキング", "🏴‍☠️ 勢力動向"])
    
    # -----------------------------------------------------
    # 🗺️ タブ1：リアルタイム海図
    # -----------------------------------------------------
    with tab_map:
        if os.path.exists(img_path):
            img = Image.open(img_path)
            
            day_map_data = full_map_data[full_map_data['通算日'] == target_day].copy()
            day_map_data = day_map_data.dropna(subset=['X_jittered', 'Y_jittered'])

            all_character_names = sorted(route_data['登場キャラ'].dropna().unique())
            day_map_data['登場キャラ'] = pd.Categorical(day_map_data['登場キャラ'], categories=all_character_names, ordered=True)

            # タイトル部分にも巻数を添えてやる粋な演出だ！
            vol_label = f" (単行本 {day_to_vol_map[target_day]} 巻)" if target_day in day_to_vol_map else ""
            fig = px.scatter(
                day_map_data,
                x="X_jittered", y="Y_jittered", color="登場キャラ",
                hover_name="表示名", text="表示用名前",
                category_orders={"登場キャラ": all_character_names},
                range_x=[-870, 870], range_y=[-476.5, 476.5],
                hover_data={'海円暦': True, '出来事': True, 'X_jittered': False, 'Y_jittered': False},
                title=f"📅 第 {target_day} 日時点のグランドライン海図{vol_label}"
            )

            fig.update_traces(marker=dict(size=8), textfont=dict(size=10), textposition='middle right', mode='markers+text')
            fig.add_layout_image(
                dict(source=img, xref="x", yref="y", x=-780, y=476.5, sizex=1740, sizey=953, sizing="stretch", opacity=1.0, layer="below")
            )
            fig.update_xaxes(dict(range=[-870, 870], autorange=False, showgrid=False, zeroline=False, visible=False))
            fig.update_yaxes(dict(range=[-476.5, 476.5], autorange=False, showgrid=False, zeroline=False, visible=False))
            fig.update_layout(height=550, margin=dict(l=0, r=0, t=40, b=0))

            st.plotly_chart(fig, use_container_width=True, config={'responsive': True})
        else:
            st.warning("海図画像が見つからねェぞ！")

    # -----------------------------------------------------
    # 💰 タブ2：ランキング
    # -----------------------------------------------------
    with tab_rank:
        vol_label = f" ({day_to_vol_map[target_day]}巻)" if target_day in day_to_vol_map else ""
        st.subheader(f"💰 時代別・懸賞金ランキング {vol_label}")
        
        if not df_bounty_log.empty:
            past_logs = df_bounty_log[df_bounty_log['通算日'] <= target_day].copy()

            if not past_logs.empty:
                latest_bounties = past_logs.sort_values(['登場キャラID', '通算日']).groupby('登場キャラID').last().reset_index()
                clean_chars = df_chars.drop_duplicates(subset=['登場キャラID'])
                ranking_df = pd.merge(latest_bounties, clean_chars, on='登場キャラID', how='left').reset_index(drop=True)

                current_year = day_to_year_map.get(target_day, 1539)
                ranking_df['生存ステータス'] = ranking_df['生存ステータス'].astype(str)
                ranking_df = ranking_df[~((ranking_df['生存ステータス'] == '1') & (current_year > ranking_df['死亡年（海円暦）']))]

                ranking_df['懸賞金'] = pd.to_numeric(ranking_df['懸賞金'], errors='coerce').fillna(0)
                ranking_df = ranking_df[ranking_df['懸賞金'] > 0].sort_values('懸賞金', ascending=False)

                if not ranking_df.empty:
                    fig_bounty = px.bar(
                        ranking_df.head(15), x='懸賞金', y='名前', orientation='h',
                        title=f"第 {target_day} 日の個人懸賞金 TOP15{vol_label}",
                        color='懸賞金', color_continuous_scale='YlOrRd', text='懸賞金'
                    )
                    fig_bounty.update_layout(yaxis={'categoryorder':'total ascending'}, height=450, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_bounty, use_container_width=True, config={'responsive': True})
                else:
                    st.info(f"第 {target_day} 日時点では、まだ誰も懸賞金がかかってねェようだ！")

        st.divider() 
        st.subheader("👑 勢力別・懸賞金総額ランキング")

        if not df_bounty_log.empty and not df_affil.empty:
            past_bounties = df_bounty_log[df_bounty_log['通算日'] <= target_day].copy()
            faction_date_col = next((col for col in ['通算日', '登場日', '話数'] if col in df_affil.columns), None)
            
            if faction_date_col is not None:
                past_factions = df_affil[df_affil[faction_date_col] <= target_day].copy()

                if not past_bounties.empty and not past_factions.empty:
                    latest_bounty = past_bounties.sort_values(['登場キャラID', '通算日']).groupby('登場キャラID').last().reset_index()[['登場キャラID', '懸賞金']]
                    latest_faction = past_factions.sort_values(['登場キャラID', faction_date_col]).groupby('登場キャラID').last().reset_index()
                    
                    if '勢力名' not in latest_faction.columns and '勢力ID' in latest_faction.columns and not df_factions.empty:
                        latest_faction = pd.merge(latest_faction, df_factions[['勢力ID', '勢力名']], on='勢力ID', how='left')
                    
                    latest_faction = latest_faction[['登場キャラID', '勢力名']]
                    merged_log_df = pd.merge(latest_bounty, latest_faction, on='登場キャラID', how='inner')
                    merged_log_df['懸賞金'] = pd.to_numeric(merged_log_df['懸賞金'], errors='coerce').fillna(0)
                    merged_log_df['勢力名'] = merged_log_df['勢力名'].fillna("無所属・その他")

                    faction_sum_df = merged_log_df.groupby('勢力名')['懸賞金'].sum().reset_index().sort_values('懸賞金', ascending=False)
                    faction_sum_df = faction_sum_df[faction_sum_df['懸賞金'] > 0]

                    if not faction_sum_df.empty:
                        fig_faction_rank = px.bar(
                            faction_sum_df.head(10), x='懸賞金', y='勢力名', orientation='h',
                            title="勢力別の現在の賞金総額", color='懸賞金', color_continuous_scale='Oranges', text='懸賞金'
                        )
                        fig_faction_rank.update_layout(yaxis={'categoryorder':'total ascending'}, height=450, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_faction_rank, use_container_width=True, config={'responsive': True})

        st.divider() 
        st.subheader("🔥 決め技ランキング")
        if not df_finisher.empty:
            fig_skill = px.bar(
                df_finisher.head(15), x='決め技カウント', y='技表示名', orientation='h',
                title="トドメを刺した回数 TOP15", color='決め技カウント', color_continuous_scale='Reds', text='決め技カウント'
            )
            fig_skill.update_layout(height=450, yaxis={'categoryorder':'total ascending'}, xaxis_title="決め技回数", yaxis_title="技名 (使用者)", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_skill, use_container_width=True, config={'responsive': True})

        st.divider() 
        st.subheader("⚔️ 技使用頻度ランキング")
        if not df_finisher.empty:
            col_rank1, col_rank2 = st.columns(2)
            with col_rank1:
                st.markdown("#### 🌍 全キャラクターの技 TOP15")
                fig_skill_all = px.bar(
                    df_finisher.head(15), x='使用回数', y='技表示名', orientation='h',
                    title="技使用頻度（全体）", color='使用回数', color_continuous_scale='Greens', text='使用回数'
                )
                fig_skill_all.update_layout(height=450, yaxis={'categoryorder':'total ascending'}, xaxis_title="使用回数", yaxis_title="技名 (使用者)", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_skill_all, use_container_width=True, config={'responsive': True})

            with col_rank2:
                st.markdown("#### 👤 キャラクター別・技ランキング")
                if not df_skills.empty:
                    available_users = sorted(df_skills['使用者'].dropna().unique().tolist())
                    selected_user = st.selectbox("キャラを選択：", available_users, key="skill_user_select")
                    
                    user_skill_df = df_skills[df_skills['使用者'] == selected_user].copy()
                    user_skill_df['使用回数'] = pd.to_numeric(user_skill_df['使用回数'], errors='coerce').fillna(0)
                    user_skill_df = user_skill_df.sort_values('使用回数', ascending=False)
                    user_skill_df = user_skill_df[user_skill_df['使用回数'] > 0]
                    
                    if not user_skill_df.empty:
                        fig_skill_user = px.bar(
                            user_skill_df, x='使用回数', y='技名', orientation='h',
                            title=f"{selected_user} の技一覧", color='使用回数', color_continuous_scale='Mint', text='使用回数'
                        )
                        dynamic_height = max(300, len(user_skill_df) * 25)
                        fig_skill_user.update_layout(height=dynamic_height, yaxis={'categoryorder':'total ascending'}, xaxis_title="使用回数", yaxis_title="技名", margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_skill_user, use_container_width=True, config={'responsive': True})

    # -----------------------------------------------------
    # 🏴‍☠️ タブ3：勢力動向
    # -----------------------------------------------------
    with tab_faction:
        vol_label = f" (単行本 {day_to_vol_map[target_day]} 巻)" if target_day in day_to_vol_map else ""
        st.subheader(f"🏴‍☠️ 勢力別名簿 ＆ キャラクター歴史比較 {vol_label}")
        
        if not faction_final.empty:
            current_roster = faction_final[faction_final['通算日'] == target_day].copy()
            
            def is_visible_roster(row):
                day = row['通算日']
                if pd.notna(row['登場日']) and day < row['登場日']: return False
                if pd.notna(row['退場日']) and day > row['退場日']: return False
                if str(row['生存ステータス']) == '1' and pd.notna(row['死亡年（海円暦）']) and row['海円暦'] > row['死亡年（海円暦）']: return False
                return True

            current_roster = current_roster[current_roster.apply(is_visible_roster, axis=1)]
            
            def get_age_display(row):
                birth = row['誕生年（海円暦）']
                if pd.isna(birth) or pd.isna(row['海円暦']): return "不明"
                if str(row['生存ステータス']) == '1' and not pd.isna(row['死亡年（海円暦）']) and row['海円暦'] >= row['死亡年（海円暦）']:
                    return f"{int(row['死亡年（海円暦）'] - birth)}歳 (故人)"
                return f"{int(row['海円暦'] - birth)}歳"
            
            current_roster['年齢'] = current_roster.apply(get_age_display, axis=1)
            
            if not current_roster.empty:
                col_sel1, col_sel2 = st.columns(2)
                with col_sel1:
                    roster_with_faction = current_roster.dropna(subset=['勢力名'])
                    available_factions = sorted(roster_with_faction['勢力名'].unique().tolist())
                    
                    default_faction_name = "麦わらの一味" if "麦わらの一味" in available_factions else available_factions[0]
                    
                    if "saved_selected_faction" not in st.session_state:
                        st.session_state["saved_selected_faction"] = default_faction_name
                    
                    if st.session_state["saved_selected_faction"] not in available_factions:
                        st.session_state["saved_selected_faction"] = available_factions[0]
                    
                    current_index = available_factions.index(st.session_state["saved_selected_faction"])
                    
                    selected_faction = st.selectbox(
                        "ベースとなる勢力を選択：", 
                        available_factions, 
                        index=current_index,
                        key="faction_selector_node"
                    )
                    st.session_state["saved_selected_faction"] = selected_faction

                with col_sel2:
                    all_available_chars = sorted(current_roster['名前'].dropna().unique().tolist())
                    selected_extra_chars = st.multiselect("同時に比較するキャラ個別追加：", all_available_chars)

                df_faction_part = current_roster[current_roster['勢力名'] == selected_faction].copy()
                df_extra_part = current_roster[current_roster['名前'].isin(selected_extra_chars)].copy()
                combined_roster = pd.concat([df_faction_part, df_extra_part]).drop_duplicates(subset=['登場キャラID'])

                day_map_info = full_map_data[full_map_data['通算日'] == target_day][['登場キャラID', '場所名', '出来事']]
                combined_roster = pd.merge(combined_roster, day_map_info, on='登場キャラID', how='left')

                total_bounty = 0
                if not df_bounty_log.empty:
                    past_b = df_bounty_log[df_bounty_log['通算日'] <= target_day].copy()
                    if not past_b.empty:
                        latest_b = past_b.sort_values(['登場キャラID', '通算日']).groupby('登場キャラID').last().reset_index()
                        member_ids = combined_roster['登場キャラID'].tolist()
                        current_bounties = latest_b[latest_b['登場キャラID'].isin(member_ids)]
                        total_bounty = current_bounties['懸賞金'].sum()

                st.markdown(f"### 📅 第 {target_day} 日時点の総合賞金額{vol_label}")
                if total_bounty > 0:
                    st.metric(label=f"🏴‍☠️ 【{selected_faction}】所属メンバー懸賞金総額", value=f"{int(total_bounty):,} ベリー")
                else:
                    st.caption(f"💡 {selected_faction} には、現在手配されているメンバーがいません！")

                display_cols = ['勢力名', '名前', '年齢', '場所名', '出来事']
                if '役職' in combined_roster.columns: display_cols.insert(2, '役職')

                display_df = combined_roster[display_cols].copy()
                display_df['勢力名'] = display_df['勢力名'].fillna("無所属・その他")
                display_df['場所名'] = display_df['場所名'].fillna("移動中または不明")
                display_df['出来事'] = display_df['出来出'] if '出来出' in combined_roster.columns else display_df['出来事'].fillna("（特にログなし）")

                st.markdown(f"### 📅 第 {target_day} 日時点の動向一覧{vol_label}")
                st.dataframe(display_df.sort_values('勢力名'), use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("#### 🔍 キャラクター詳細ビュアー")
                char_names = combined_roster['名前'].tolist()
                selected_char_name = st.selectbox("詳細を見たいキャラを選択：", ["（選択してください）"] + char_names)

                if selected_char_name != "（選択してください）":
                    char_info = combined_roster[combined_roster['名前'] == selected_char_name].iloc[0]
                    selected_cid = char_info['登場キャラID']

                    with st.container(border=True):
                        st.subheader(f"🏴‍☠️ {selected_char_name} の詳細")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**【役職・肩書】** {char_info.get('役職', 'なし')}")
                            st.write(f"**【年齢】** {char_info['年齢']}")
                            char_master = df_chars[df_chars['登場キャラID'] == selected_cid]
                            origin_place = char_master.iloc[0]['出身島・国'] if not char_master.empty and '出身島・国' in df_chars.columns else "不明"
                            st.write(f"**【出身地】** {origin_place}")
                        with col2:
                            st.write(f"**【現在位置】** 🗺️ {char_info.get('場所名', '移動中または不明')}")
                            if not df_bounty_log.empty:
                                past_b = df_bounty_log[df_bounty_log['通算日'] <= target_day].copy()
                                char_bounty_idx = past_b[past_b['登場キャラID'] == selected_cid].sort_values('通算日').last_valid_index()
                                if char_bounty_idx is not None:
                                    b_val = past_b.loc[char_bounty_idx, '懸賞金']
                                    st.write(f"**【現在の懸賞金】** 🪙 {int(b_val):,} ベリー" if b_val > 0 else "**【現在の懸賞金】** 手配書なし (0ベリー)")
                                else:
                                    st.write("**【現在の懸賞金】** 手配書なし")

                        st.markdown("---")
                        st.markdown("**【🔥 これまでに使った技の一覧】**")
                        if not df_skills.empty:
                            char_skills_df = df_skills[df_skills['使用者'] == selected_char_name]
                            if '通算日' in char_skills_df.columns:
                                char_skills_df = char_skills_df[char_skills_df['通算日'] <= target_day]
                            if not char_skills_df.empty:
                                for _, s_row in char_skills_df.iterrows(): st.write(f"・ **{s_row['技名']}** ")
                            else:
                                st.caption(" まだこのキャラの決め技データはマスタに登録されていねェようだ！")
            else:
                st.info(f"第 {target_day} 日時点では、表示できるメンバーはいねェようだ！")
except Exception as e:
    st.error(f"エラーが発生したぞ！：{e}")
