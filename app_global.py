import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="全範圍積分計算工具 (最低點 Baseline)", layout="wide")

st.title("全範圍積分計算工具 (最低點 Baseline)")

# Sidebar for parameters
st.sidebar.header("參數設定")

uploaded_file = st.sidebar.file_uploader("上傳 Excel 檔案", type=["xlsx"], help="請上傳包含 Q 欄位與各時間點 Intensity 的 Excel 檔案。")

input_path = uploaded_file if uploaded_file else None

st.sidebar.subheader("Baseline 設定")
baseline_mode = st.sidebar.radio(
    "Baseline 模式",
    ["全資料指定區間最低點 (Global Min in Range)", "單一時間點指定區間最低點 (Local Min in Range)"],
    help="選擇如何決定 Baseline 的最低點。"
)

baseline_q_min = st.sidebar.number_input("Baseline Q 值下限", value=0.1, step=0.1, help="尋找 Baseline 最低點的 Q 值左邊界")
baseline_q_max = st.sidebar.number_input("Baseline Q 值上限", value=0.5, step=0.1, help="尋找 Baseline 最低點的 Q 值右邊界")

if st.sidebar.button("開始分析"):
    if not input_path:
        st.error("請上傳 Excel 檔案以開始分析。")
    else:
        with st.spinner("讀取資料並計算中..."):
            df = pd.read_excel(input_path, engine='openpyxl')
            
            q_vals = df['Q'].values
            cols = df.columns[1:]
            
            # 直接取最高和最低 Q 值作為全範圍
            q_min = q_vals.min()
            q_max = q_vals.max()
            search_mask = (q_vals >= q_min) & (q_vals <= q_max) # 實際上這會是所有點 (True)
            q_calc = q_vals[search_mask]
            
            if len(q_calc) < 2:
                st.error("資料點不足，無法計算。")
                st.stop()
            
            # Baseline 區間 Mask
            baseline_mask = (q_vals >= baseline_q_min) & (q_vals <= baseline_q_max)
            if not any(baseline_mask):
                st.error("在設定的 Baseline Q 範圍內沒有資料點，無法決定 Baseline。")
                st.stop()
                
            # 決定 Global Min
            if baseline_mode == "全資料指定區間最低點 (Global Min in Range)":
                global_min = df.iloc[:, 1:][baseline_mask].values.min()
            
            results = {'Time_or_Col': [], 'Total_Area': []}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 準備繪圖 (取 5 個時間點)
            num_cols = len(cols)
            plot_indices = np.linspace(0, num_cols - 1, min(5, num_cols)).astype(int)
            plot_data = []
            
            for idx, col in enumerate(cols):
                results['Time_or_Col'].append(col)
                y_vals = df[col].values
                y_calc = y_vals[search_mask]
                
                if baseline_mode == "全資料指定區間最低點 (Global Min in Range)":
                    baseline = np.full_like(y_calc, global_min)
                else:
                    local_min = y_vals[baseline_mask].min()
                    baseline = np.full_like(y_calc, local_min)
                
                y_above_baseline = np.maximum(y_calc - baseline, 0)
                
                if hasattr(np, 'trapezoid'):
                    area = np.trapezoid(y_above_baseline, q_calc)
                else:
                    area = np.trapz(y_above_baseline, q_calc)
                    
                results['Total_Area'].append(area)
                
                # 儲存繪圖資料
                if idx in plot_indices:
                    plot_data.append({
                        'col_name': col,
                        'y_vals': y_vals,
                        'baseline_val': baseline[0]
                    })
                    
                if idx % max(1, len(cols)//10) == 0:
                    progress_bar.progress((idx + 1) / len(cols))
                    status_text.text(f"正在處理資料欄位: {idx+1}/{len(cols)}")
                    
            progress_bar.progress(1.0)
            status_text.text("計算完成！")
            
            results_df = pd.DataFrame(results)
            st.subheader("面積計算結果")
            st.dataframe(results_df)
            
            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button("下載計算結果 (CSV)", data=csv, file_name="total_area_results.csv", mime="text/csv")
            
            # Validation Plots
            st.subheader("驗證圖表 (取 5 個時間點)")
            
            cols_ui = st.columns(len(plot_data))
            
            for ui_col, p_data in zip(cols_ui, plot_data):
                # 提高 dpi (解析度) 設定
                fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
                
                y_plot = p_data['y_vals']
                y_calc_plot = y_plot[search_mask]
                b_val = p_data['baseline_val']
                
                ax.plot(q_vals, y_plot, label='Data', color='black', alpha=0.7)
                
                # 畫 baseline
                ax.plot(q_calc, np.full_like(q_calc, b_val), color='red', linestyle='--', linewidth=1.5, label='Baseline')
                
                # 塗色積分區域
                ax.fill_between(q_calc, b_val, np.maximum(y_calc_plot, b_val), color='blue', alpha=0.3)
                
                ax.set_xlim(q_min, q_max)
                
                # 設定 log 軸
                ax.set_yscale('log')
                
                if any(search_mask):
                    # 對數座標不支援負數或零，需要給一個很小的正數作為下界
                    min_y = max(1e-10, b_val * 0.5 if b_val > 0 else np.min(y_calc_plot[y_calc_plot > 0]) * 0.5)
                    ax.set_ylim(min_y, np.max(y_calc_plot) * 1.5)
                
                ax.set_xlabel('Q')
                ax.set_ylabel('Intensity (log)')
                ax.set_title(str(p_data['col_name']))
                
                ui_col.pyplot(fig)
                plt.close(fig)
