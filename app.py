import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import os

st.set_page_config(page_title="峰面積計算工具", layout="wide")

st.title("峰面積計算工具")

# Sidebar for parameters

st.sidebar.header("參數設定")

uploaded_file = st.sidebar.file_uploader("上傳 Excel 檔案", type=["xlsx"], help="請上傳包含 Q 欄位與各時間點 Intensity 的 Excel 檔案。若未上傳會請您先提供檔案。")
default_file = "all_data.xlsx"

input_path = uploaded_file if uploaded_file else None

st.sidebar.subheader("尋峰設定")
q_min = st.sidebar.number_input("Q 值下限", value=0.4, step=0.1, help="限定尋找 Peak 的 Q 值左邊界")
q_max = st.sidebar.number_input("Q 值上限", value=1.4, step=0.1, help="限定尋找 Peak 的 Q 值右邊界")
prominence = st.sidebar.number_input("凸顯度 (Prominence)", value=0.0015, step=0.0001, format="%.4f", help="決定 Peak 相對於周圍背景的突出程度。數值太小容易抓到雜訊，太大可能會漏掉真實的 Peak。")
distance = st.sidebar.number_input("最小距離 (Distance)", value=10, step=1, help="兩個相鄰 Peak 之間最少需要間隔多少個資料點，可用來避免在同一個寬峰上重複抓到多個 Peak。")

if st.sidebar.button("開始分析"):
    if not input_path:
        st.error("請上傳 Excel 檔案以開始分析。")
    else:
        with st.spinner("讀取資料並計算中... 可能需要一些時間。"):
            df = pd.read_excel(input_path, engine='openpyxl')
            
            q_vals = df['Q'].values
            cols = df.columns[1:]
            
            # 尋峰標準點
            ref_idx = int(len(cols) * 4 / 5)
            ref_col = cols[ref_idx]
            y_ref = df[ref_col].values
            
            search_mask = (q_vals >= q_min) & (q_vals <= q_max)
            q_search = q_vals[search_mask]
            y_search = y_ref[search_mask]
            
            peaks, properties = find_peaks(y_search, prominence=prominence, distance=distance)
            
            peak_regions = {}
            for i, peak_idx in enumerate(peaks):
                actual_peak_idx = np.where(search_mask)[0][peak_idx]
                peak_q = q_vals[actual_peak_idx]
                
                radius_idx = 15
                start_idx = max(0, actual_peak_idx - radius_idx)
                end_idx = min(len(q_vals) - 1, actual_peak_idx + radius_idx)
                
                peak_name = f'Peak_{i+1}_(~{peak_q:.2f})'
                peak_regions[peak_name] = (q_vals[start_idx], q_vals[end_idx])
            
            st.success(f"成功偵測到 {len(peak_regions)} 個 Peaks: {list(peak_regions.keys())}")
            
            results = {'Time_or_Col': []}
            for peak_name in peak_regions.keys():
                results[peak_name] = []
                
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, col in enumerate(cols):
                results['Time_or_Col'].append(col)
                y_vals = df[col].values
                
                for peak_name, (q_start, q_end) in peak_regions.items():
                    mask = (q_vals >= q_start) & (q_vals <= q_end)
                    q_peak = q_vals[mask]
                    y_peak = y_vals[mask]
                    
                    if len(q_peak) < 2:
                        results[peak_name].append(0)
                        continue
                        
                    mid_idx = len(q_peak) // 2
                    left_min_idx = np.argmin(y_peak[:mid_idx])
                    right_min_idx = mid_idx + np.argmin(y_peak[mid_idx:])
                    
                    q_start_actual = q_peak[left_min_idx]
                    q_end_actual = q_peak[right_min_idx]
                    y_start_actual = y_peak[left_min_idx]
                    y_end_actual = y_peak[right_min_idx]
                    
                    calc_mask = (q_peak >= q_start_actual) & (q_peak <= q_end_actual)
                    q_calc = q_peak[calc_mask]
                    y_calc = y_peak[calc_mask]
                    
                    if len(q_calc) < 2:
                         results[peak_name].append(0)
                         continue
                    
                    if q_end_actual != q_start_actual:
                        slope = (y_end_actual - y_start_actual) / (q_end_actual - q_start_actual)
                    else:
                        slope = 0
                    intercept = y_start_actual - slope * q_start_actual
                    baseline = slope * q_calc + intercept
                    
                    y_above_baseline = np.maximum(y_calc - baseline, 0)
                    
                    if hasattr(np, 'trapezoid'):
                        area = np.trapezoid(y_above_baseline, q_calc)
                    else:
                        area = np.trapz(y_above_baseline, q_calc)
                    results[peak_name].append(area)
                    
                if idx % max(1, len(cols)//10) == 0:
                    progress_bar.progress((idx + 1) / len(cols))
                    status_text.text(f"正在處理資料欄位: {idx+1}/{len(cols)}")
                    
            progress_bar.progress(1.0)
            status_text.text("計算完成！")
            
            results_df = pd.DataFrame(results)
            st.subheader("面積計算結果")
            st.dataframe(results_df)
            
            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button("下載計算結果 (CSV)", data=csv, file_name="calculated_peak_areas.csv", mime="text/csv")
            
            # Validation Plots
            st.subheader("驗證圖表 (取 5 個時間點)")
            
            num_cols = len(cols)
            # 等距取 5 個點
            plot_indices = np.linspace(0, num_cols - 1, 5).astype(int)
            plot_labels = [f"Point {idx+1}" for idx in range(5)]
            
            import matplotlib.cm as cm
            colors_map = cm.rainbow(np.linspace(0, 1, len(peak_regions)))
            
            cols_ui = st.columns(5)
            
            for ui_col, p_idx, p_label in zip(cols_ui, plot_indices, plot_labels):
                col_name = cols[p_idx]
                y_vals = df[col_name].values
                
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.plot(q_vals, y_vals, label=f'Data', color='black', alpha=0.5)
                
                for i, (peak_name, (q_start, q_end)) in enumerate(peak_regions.items()):
                    mask = (q_vals >= q_start) & (q_vals <= q_end)
                    q_peak = q_vals[mask]
                    y_peak = y_vals[mask]
                    
                    if len(q_peak) >= 2:
                        m_idx = len(q_peak) // 2
                        l_min_idx = np.argmin(y_peak[:m_idx])
                        r_min_idx = m_idx + np.argmin(y_peak[m_idx:])
                        
                        q_s_actual = q_peak[l_min_idx]
                        q_e_actual = q_peak[r_min_idx]
                        y_s_actual = y_peak[l_min_idx]
                        y_e_actual = y_peak[r_min_idx]
                        
                        calc_mask = (q_peak >= q_s_actual) & (q_peak <= q_e_actual)
                        q_calc = q_peak[calc_mask]
                        y_calc = y_peak[calc_mask]
                        
                        if len(q_calc) >= 2:
                            if q_e_actual != q_s_actual:
                                slope = (y_e_actual - y_s_actual) / (q_e_actual - q_s_actual)
                            else:
                                slope = 0
                            intercept = y_s_actual - slope * q_s_actual
                            baseline = slope * q_calc + intercept
                            
                            ax.fill_between(q_calc, baseline, np.maximum(y_calc, baseline), color=colors_map[i], alpha=0.5)
                            ax.plot(q_calc, baseline, color='red', linestyle='--', linewidth=1)
                
                ax.set_xlim(q_min, q_max)
                mask_plot = (q_vals >= q_min) & (q_vals <= q_max)
                if any(mask_plot):
                    ax.set_ylim(0, np.max(y_vals[mask_plot]) * 1.1)
                
                ax.set_xlabel('Q')
                ax.set_ylabel('Intensity')
                ax.set_title(f"{p_label}: {col_name}")
                
                ui_col.pyplot(fig)
                plt.close(fig)
