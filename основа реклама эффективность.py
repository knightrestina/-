import streamlit as st
import pandas as pd
import numpy as np
import re
import datetime
from io import BytesIO
import base64

# Настройка страницы
st.set_page_config(
    page_title="Анализ эффективности рекламы",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #2563EB;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #F0F9FF;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #3B82F6;
        margin-bottom: 1rem;
    }
    .delete-card {
        background-color: #FEF2F2;
        border-left: 5px solid #DC2626;
    }
    .scale-card {
        background-color: #F0FDF4;
        border-left: 5px solid #16A34A;
    }
    .optimize-card {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    .stProgress > div > div > div > div {
        background-color: #3B82F6;
    }
</style>
""", unsafe_allow_html=True)

# Заголовок приложения
st.markdown('<h1 class="main-header">📊 Анализ эффективности рекламных объявлений</h1>', unsafe_allow_html=True)
st.markdown("---")

# Инициализация состояния сессии
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'result_sorted' not in st.session_state:
    st.session_state.result_sorted = None
if 'delete_ads' not in st.session_state:
    st.session_state.delete_ads = None
if 'scale_ads' not in st.session_state:
    st.session_state.scale_ads = None
if 'optimize_ads' not in st.session_state:
    st.session_state.optimize_ads = None
if 'summary_stats' not in st.session_state:
    st.session_state.summary_stats = None

# Функции для обработки данных
def normalize_column_names(df):
    rename_dict = {}
    for col in df.columns:
        clean_col = col.strip()
        clean_col = re.sub(r'\s+', ' ', clean_col)
        clean_col = re.sub(r'\s*,\s*', ', ', clean_col)
        rename_dict[col] = clean_col
    return df.rename(columns=rename_dict)

def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None

def classify_source(source):
    if pd.isna(source) or source == '' or source == ' ':
        return 'Другое'
    
    source_str = str(source).lower().strip()
    
    if re.match(r'^\d+$', source_str):
        return 'Рекламное объявление'
    
    organic_keywords = [
        'organic', 'direct', 'none', 'null', 'undefined', 
        'сайт', 'site', 'organic', 'прямой', 'рекомендация',
        'recommendation', 'поиск', 'search', 'google', 'yandex',
        'соцсети', 'social', 'vk', 'facebook', 'instagram',
        'telegram', 'whatsapp', 'email', 'рассылка', 'unknown',
        'не указано', 'другое', 'other'
    ]
    
    for keyword in organic_keywords:
        if keyword in source_str:
            return 'Другое'
    
    if not re.match(r'^\d+$', source_str):
        return 'Другое'
    
    return 'Рекламное объявление'

def determine_recommendation(row, has_revenue_data, avg_conversion, avg_roi, avg_cpo, avg_leads):
    recommendations = []
    
    if row['Количество заказов'] == 0:
        recommendations.append("УДАЛИТЬ - нет заказов")
        return "; ".join(recommendations)
    
    if has_revenue_data:
        if row['ROI, %'] < 0:
            recommendations.append("УДАЛИТЬ - отрицательный ROI")
        elif row['ROI, %'] < 50:
            recommendations.append("ОПТИМИЗИРОВАТЬ - низкий ROI")
        
        if row['ROI, %'] > 150:
            recommendations.append("МАСШТАБИРОВАТЬ - высокий ROI")
        
        if row['Прибыль'] > 10000 and row['ROI, %'] > 100:
            recommendations.append("МАСШТАБИРОВАТЬ - высокая прибыль и ROI")
    else:
        if row['Конверсия, %'] == 0:
            recommendations.append("УДАЛИТЬ - нулевая конверсия")
        elif row['Конверсия, %'] < avg_conversion * 0.5:
            recommendations.append("ОПТИМИЗИРОВАТЬ - конверсия ниже среднего")
        
        if row['Конверсия, %'] > 30:
            recommendations.append("МАСШТАБИРОВАТЬ - высокая конверсия")
        
        if row['Лиды'] > avg_leads * 2 and row['Конверсия, %'] > avg_conversion:
            recommendations.append("МАСШТАБИРОВАТЬ - много лидов и хорошая конверсия")
    
    if row['CPO, ₽'] > avg_cpo * 3 and row['CPO, ₽'] > 0:
        recommendations.append("ОПТИМИЗИРОВАТЬ - высокая стоимость заказа")
    
    if row['Лиды'] < 10 and row['Количество заказов'] == 0:
        recommendations.append("ТЕСТИРОВАТЬ - мало данных")
    
    if not recommendations:
        recommendations.append("НАБЛЮДАТЬ - стабильные показатели")
    
    return "; ".join(recommendations)

def create_excel_report(result_sorted, delete_ads, scale_ads, optimize_ads, summary_stats):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_sorted.to_excel(writer, sheet_name='Все объявления с рекомендациями', index=False)
        if delete_ads is not None and not delete_ads.empty:
            delete_ads.to_excel(writer, sheet_name='УДАЛИТЬ', index=False)
        if scale_ads is not None and not scale_ads.empty:
            scale_ads.to_excel(writer, sheet_name='МАСШТАБИРОВАТЬ', index=False)
        if optimize_ads is not None and not optimize_ads.empty:
            optimize_ads.to_excel(writer, sheet_name='ОПТИМИЗИРОВАТЬ', index=False)
    output.seek(0)
    return output

# Сайдбар для загрузки файлов
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2092/2092655.png", width=100)
    st.markdown("### 📁 Загрузка данных")
    
    st.markdown("#### Рекламные данные")
    st.markdown("Нужные столбцы:")
    st.markdown("- **ID объявления**")
    st.markdown("- **Результат** (количество лидов)")
    st.markdown("- **Потрачено всего, ₽**")
    st.markdown("- **Цена за результат, ₽** (опционально)")
    
    uploaded_ads = st.file_uploader("Выберите файл с рекламными данными", 
                                   type=['csv', 'xlsx', 'xls'],
                                   key="ads_uploader")
    
    st.markdown("---")
    
    st.markdown("#### CRM данные")
    st.markdown("Нужные столбцы:")
    st.markdown("- **Клиенты**")
    st.markdown("- **ID объявления**")
    st.markdown("- **Сумма заказов** (опционально)")
    
    uploaded_crm = st.file_uploader("Выберите файл с CRM данными", 
                                   type=['csv', 'xlsx', 'xls'],
                                   key="crm_uploader")
    
    st.markdown("---")
    
    if st.button("🚀 Запустить анализ", type="primary", use_container_width=True):
        if uploaded_ads is not None and uploaded_crm is not None:
            st.session_state.analysis_done = True
            st.rerun()
        else:
            st.error("Пожалуйста, загрузите оба файла")
    
    st.markdown("---")
    st.markdown("### ℹ️ О программе")
    st.markdown("""
    Программа анализирует эффективность 
    рекламных объявлений, вычисляет конверсию,
    ROI и дает рекомендации по оптимизации.
    """)

# Основная область
if not st.session_state.analysis_done:
    # Приветственный экран
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🎯 Как это работает")
        st.info("""
        1. Загрузите файлы из рекламного кабинета и CRM системы
        2. Нажмите кнопку "Запустить анализ"
        3. Получите детальный отчет и рекомендации
        """)
        
        st.markdown("### 📋 Примеры форматов данных")
        
        with st.expander("Рекламные данные (пример)"):
            example_ads = pd.DataFrame({
                'ID объявления': [12345, 12346, 12347],
                'Результат': [150, 200, 75],
                'Цена за результат, ₽': [300, 250, 400],
                'Потрачено всего, ₽': [45000, 50000, 30000]
            })
            st.dataframe(example_ads)
        
        with st.expander("CRM данные (пример)"):
            example_crm = pd.DataFrame({
                'Клиенты': ['Клиент 1', 'Клиент 2', 'Клиент 3'],
                'ID объявления': [12345, 12345, 12346],
                'Сумма заказов': [5000, 7500, 3000]
            })
            st.dataframe(example_crm)
    
else:
    # Запуск анализа
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Чтение файлов
        status_text.text("Чтение файлов...")
        progress_bar.progress(10)
        
        if uploaded_ads.name.endswith('.csv'):
            ads_data = pd.read_csv(uploaded_ads)
        else:
            ads_data = pd.read_excel(uploaded_ads)
            
        if uploaded_crm.name.endswith('.csv'):
            crm_data = pd.read_csv(uploaded_crm)
        else:
            crm_data = pd.read_excel(uploaded_crm)
        
        # Нормализация названий столбцов
        status_text.text("Обработка данных...")
        progress_bar.progress(20)
        
        ads_data = normalize_column_names(ads_data)
        crm_data = normalize_column_names(crm_data)
        
        # Поиск столбцов
        ads_columns_mapping = {
            'id': ['ID объявления', 'ID', 'Ad ID', 'AdID', 'ID рекламы', 'ID кампании'],
            'leads': ['Результат', 'Лиды', 'Leads', 'Клики', 'Clicks', 'Конверсии'],
            'cost_per_lead': ['Цена за результат, ₽', 'Цена за результат', 'Cost per Result', 'CPL', 'Цена за лид'],
            'spent': ['Потрачено всего, ₽', 'Потрачено', 'Затраты', 'Spent', 'Cost', 'Расходы']
        }
        
        crm_columns_mapping = {
            'clients': ['Клиенты', 'Клиент', 'Client', 'Customers', 'Заказчики'],
            'id': ['ID объявления', 'ID', 'Ad ID', 'AdID', 'ID рекламы', 'Источник'],
            'revenue': ['Сумма заказов', 'Сумма заказа', 'Сумма', 'Заказ', 'Revenue', 'Выручка', 'Amount']
        }
        
        ads_actual_columns = {}
        crm_actual_columns = {}
        
        for key, possible_names in ads_columns_mapping.items():
            found_col = find_column(ads_data, possible_names)
            if found_col:
                ads_actual_columns[key] = found_col
        
        for key, possible_names in crm_columns_mapping.items():
            found_col = find_column(crm_data, possible_names)
            if found_col:
                crm_actual_columns[key] = found_col
        
        # Проверка обязательных столбцов
        required_ads = ['id', 'leads', 'spent']
        required_crm = ['id', 'clients']
        
        missing_ads = [col for col in required_ads if col not in ads_actual_columns]
        missing_crm = [col for col in required_crm if col not in crm_actual_columns]
        
        if missing_ads or missing_crm:
            st.error(f"Отсутствуют обязательные столбцы: {missing_ads + missing_crm}")
            st.stop()
        
        has_revenue_data = 'revenue' in crm_actual_columns
        
        # Подготовка данных
        status_text.text("Подготовка данных...")
        progress_bar.progress(40)
        
        ads_rename_dict = {v: k for k, v in ads_actual_columns.items()}
        crm_rename_dict = {v: k for k, v in crm_actual_columns.items()}
        
        ads_data_clean = ads_data.rename(columns=ads_rename_dict)
        crm_data_clean = crm_data.rename(columns=crm_rename_dict)
        
        # Классификация источников
        crm_data_clean['Тип источника'] = crm_data_clean['id'].apply(classify_source)
        crm_reklama = crm_data_clean[crm_data_clean['Тип источника'] == 'Рекламное объявление'].copy()
        crm_drugoe = crm_data_clean[crm_data_clean['Тип источника'] == 'Другое'].copy()
        
        # Агрегация рекламных данных
        status_text.text("Анализ данных...")
        progress_bar.progress(60)
        
        agg_dict = {'leads': 'sum', 'spent': 'sum'}
        if 'cost_per_lead' in ads_data_clean.columns:
            agg_dict['cost_per_lead'] = 'mean'
        
        ads_aggregated = ads_data_clean.groupby('id', as_index=False).agg(agg_dict)
        
        # Агрегация CRM данных
        if has_revenue_data:
            crm_reklama_agg = crm_reklama.groupby('id').agg({
                'clients': 'count',
                'revenue': ['sum', 'mean']
            }).round(2)
            crm_reklama_agg.columns = ['Количество заказов', 'Общая выручка', 'Средний чек']
            crm_reklama_agg = crm_reklama_agg.reset_index()
        else:
            orders_count_reklama = crm_reklama.groupby('id').size().reset_index(name='Количество заказов')
            crm_reklama_agg = orders_count_reklama
        
        # Объединение данных
        merged_data = pd.merge(ads_aggregated, crm_reklama_agg, on='id', how='left')
        
        if has_revenue_data:
            merged_data['Количество заказов'] = merged_data['Количество заказов'].fillna(0).astype(int)
            merged_data['Общая выручка'] = merged_data['Общая выручка'].fillna(0)
            merged_data['Средний чек'] = merged_data['Средний чек'].fillna(0)
        else:
            merged_data['Количество заказов'] = merged_data['Количество заказов'].fillna(0).astype(int)
        
        # Расчет метрик
        merged_data['Конверсия, %'] = (merged_data['Количество заказов'] / merged_data['leads'] * 100).round(2)
        merged_data['CPO, ₽'] = (merged_data['spent'] / merged_data['Количество заказов'])
        merged_data['CPO, ₽'] = merged_data['CPO, ₽'].replace([float('inf'), -float('inf')], 0).round(2)
        merged_data['CPL, ₽'] = (merged_data['spent'] / merged_data['leads']).round(2)
        
        if has_revenue_data:
            merged_data['ROI, %'] = ((merged_data['Общая выручка'] - merged_data['spent']) / merged_data['spent'] * 100).round(2)
            merged_data['Прибыль'] = (merged_data['Общая выручка'] - merged_data['spent']).round(2)
            merged_data['ROMI'] = (merged_data['Общая выручка'] / merged_data['spent']).round(2)
        
        # Переименование для вывода
        output_columns_rename = {'id': 'ID объявления', 'leads': 'Лиды', 'spent': 'Затраты, ₽'}
        if 'cost_per_lead' in ads_data_clean.columns:
            output_columns_rename['cost_per_lead'] = 'Цена за лид, ₽'
        
        merged_data_output = merged_data.rename(columns=output_columns_rename)
        
        # Определение рекомендаций
        status_text.text("Формирование рекомендаций...")
        progress_bar.progress(80)
        
        if has_revenue_data:
            avg_roi = merged_data_output[merged_data_output['ROI, %'] != 0]['ROI, %'].mean()
        else:
            avg_roi = 0
        
        avg_conversion = merged_data_output[merged_data_output['Конверсия, %'] != 0]['Конверсия, %'].mean()
        avg_cpo = merged_data_output[(merged_data_output['CPO, ₽'] != 0) & (merged_data_output['CPO, ₽'] < 100000)]['CPO, ₽'].mean()
        avg_leads = merged_data_output['Лиды'].mean()
        
        merged_data_output['Рекомендация'] = merged_data_output.apply(
            lambda row: determine_recommendation(row, has_revenue_data, avg_conversion, avg_roi, avg_cpo, avg_leads), 
            axis=1
        )
        
        # Создание категорий
        delete_ads = merged_data_output[merged_data_output['Рекомендация'].str.contains('УДАЛИТЬ')].copy()
        scale_ads = merged_data_output[merged_data_output['Рекомендация'].str.contains('МАСШТАБИРОВАТЬ')].copy()
        optimize_ads = merged_data_output[merged_data_output['Рекомендация'].str.contains('ОПТИМИЗИРОВАТЬ')].copy()
        
        # Сортировка
        if has_revenue_data:
            sort_columns = ['ROI, %', 'Конверсия, %']
        else:
            sort_columns = ['Конверсия, %']
        
        result_sorted = merged_data_output.sort_values(sort_columns, ascending=[False, False])
        
        # Расчет статистики
        total_leads = ads_aggregated['leads'].sum()
        total_orders_reklama = crm_reklama_agg['Количество заказов'].sum() if has_revenue_data else orders_count_reklama['Количество заказов'].sum()
        total_orders_drugoe = len(crm_drugoe)
        total_spent = ads_aggregated['spent'].sum()
        
        avg_conversion_reklama = (total_orders_reklama / total_leads * 100) if total_leads > 0 else 0
        
        if has_revenue_data:
            total_revenue_reklama = crm_reklama_agg['Общая выручка'].sum()
            total_profit_reklama = total_revenue_reklama - total_spent
            overall_roi_reklama = (total_profit_reklama / total_spent * 100) if total_spent > 0 else 0
        
        # Сохранение в session state
        st.session_state.result_sorted = result_sorted
        st.session_state.delete_ads = delete_ads
        st.session_state.scale_ads = scale_ads
        st.session_state.optimize_ads = optimize_ads
        st.session_state.summary_stats = {
            'total_leads': total_leads,
            'total_orders_reklama': total_orders_reklama,
            'total_orders_drugoe': total_orders_drugoe,
            'total_spent': total_spent,
            'avg_conversion_reklama': avg_conversion_reklama,
            'has_revenue_data': has_revenue_data,
            'total_revenue_reklama': total_revenue_reklama if has_revenue_data else 0,
            'total_profit_reklama': total_profit_reklama if has_revenue_data else 0,
            'overall_roi_reklama': overall_roi_reklama if has_revenue_data else 0
        }
        
        status_text.text("Анализ завершен!")
        progress_bar.progress(100)
        
    except Exception as e:
        st.error(f"Произошла ошибка при анализе: {str(e)}")
        st.stop()
    
    # Отображение результатов
    st.markdown('<h2 class="sub-header">📈 Результаты анализа</h2>', unsafe_allow_html=True)
    
    # Сводная статистика
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Всего лидов", f"{st.session_state.summary_stats['total_leads']:,}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Заказов из рекламы", f"{st.session_state.summary_stats['total_orders_reklama']:,}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Общие затраты", f"{st.session_state.summary_stats['total_spent']:,.0f} ₽")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Конверсия", f"{st.session_state.summary_stats['avg_conversion_reklama']:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.summary_stats['has_revenue_data']:
        col5, col6, col7 = st.columns(3)
        
        with col5:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Общая выручка", f"{st.session_state.summary_stats['total_revenue_reklama']:,.0f} ₽")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col6:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Прибыль", f"{st.session_state.summary_stats['total_profit_reklama']:,.0f} ₽")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col7:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Общий ROI", f"{st.session_state.summary_stats['overall_roi_reklama']:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Распределение рекомендаций
    st.markdown('<h3 class="sub-header">🎯 Распределение рекомендаций</h3>', unsafe_allow_html=True)
    
    total_ads = len(st.session_state.result_sorted)
    delete_count = len(st.session_state.delete_ads) if st.session_state.delete_ads is not None else 0
    scale_count = len(st.session_state.scale_ads) if st.session_state.scale_ads is not None else 0
    optimize_count = len(st.session_state.optimize_ads) if st.session_state.optimize_ads is not None else 0
    other_count = total_ads - delete_count - scale_count - optimize_count
    
    cols = st.columns(4)
    
    with cols[0]:
        st.markdown(f'<div class="metric-card delete-card">', unsafe_allow_html=True)
        st.markdown(f"#### ❌ Удалить")
        st.markdown(f"**{delete_count}** объявлений")
        st.markdown(f"({delete_count/total_ads*100:.1f}%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with cols[1]:
        st.markdown(f'<div class="metric-card scale-card">', unsafe_allow_html=True)
        st.markdown(f"#### 🚀 Масштабировать")
        st.markdown(f"**{scale_count}** объявлений")
        st.markdown(f"({scale_count/total_ads*100:.1f}%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with cols[2]:
        st.markdown(f'<div class="metric-card optimize-card">', unsafe_allow_html=True)
        st.markdown(f"#### ⚡ Оптимизировать")
        st.markdown(f"**{optimize_count}** объявлений")
        st.markdown(f"({optimize_count/total_ads*100:.1f}%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown(f'<div class="metric-card">', unsafe_allow_html=True)
        st.markdown(f"#### 👁️ Наблюдать")
        st.markdown(f"**{other_count}** объявлений")
        st.markdown(f"({other_count/total_ads*100:.1f}%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Детальные таблицы
    st.markdown('<h3 class="sub-header">📋 Детальный анализ</h3>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["Все объявления", "Удалить", "Масштабировать", "Оптимизировать"])
    
    with tab1:
        st.dataframe(st.session_state.result_sorted, use_container_width=True)
    
    with tab2:
        if st.session_state.delete_ads is not None and not st.session_state.delete_ads.empty:
            st.dataframe(st.session_state.delete_ads, use_container_width=True)
            
            # Потенциальная экономия
            if 'Затраты, ₽' in st.session_state.delete_ads.columns:
                total_spent_delete = st.session_state.delete_ads['Затраты, ₽'].sum()
                st.info(f"💰 **Потенциальная экономия:** {total_spent_delete:,.0f} ₽")
        else:
            st.success("🎉 Нет объявлений для удаления!")
    
    with tab3:
        if st.session_state.scale_ads is not None and not st.session_state.scale_ads.empty:
            st.dataframe(st.session_state.scale_ads, use_container_width=True)
            
            # Потенциальная прибыль
            if st.session_state.summary_stats['has_revenue_data'] and 'Прибыль' in st.session_state.scale_ads.columns:
                total_profit_scale = st.session_state.scale_ads['Прибыль'].sum()
                st.success(f"🚀 **Текущая прибыль:** {total_profit_scale:,.0f} ₽")
                st.success(f"📈 **Потенциальная прибыль (+50%):** {total_profit_scale * 1.5:,.0f} ₽")
        else:
            st.warning("🤔 Нет объявлений для масштабирования")
    
    with tab4:
        if st.session_state.optimize_ads is not None and not st.session_state.optimize_ads.empty:
            st.dataframe(st.session_state.optimize_ads, use_container_width=True)
            
            # Советы по оптимизации
            st.info("""
            **Советы по оптимизации:**
            1. Проверьте целевые аудитории
            2. Оптимизируйте креативы
            3. Настройте ставки
            4. Протестируйте разные форматы
            """)
        else:
            st.success("🎉 Нет объявлений для оптимизации!")
    
    # Экспорт результатов
    st.markdown('<h3 class="sub-header">📥 Экспорт результатов</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Создание Excel файла
        excel_data = create_excel_report(
            st.session_state.result_sorted,
            st.session_state.delete_ads,
            st.session_state.scale_ads,
            st.session_state.optimize_ads,
            st.session_state.summary_stats
        )
        
        st.download_button(
            label="📊 Скачать Excel отчет",
            data=excel_data,
            file_name=f"рекламный_анализ_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col2:
        if st.button("🔄 Новый анализ", use_container_width=True):
            st.session_state.analysis_done = False
            st.session_state.result_sorted = None
            st.session_state.delete_ads = None
            st.session_state.scale_ads = None
            st.session_state.optimize_ads = None
            st.session_state.summary_stats = None
            st.rerun()
    
    # Информация о данных
    with st.expander("📊 Информация о загруженных данных"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Рекламные данные:**")
            st.write(f"- Объявлений: {len(ads_data_clean)}")
            st.write(f"- Строк: {len(ads_data)}")
            st.write(f"- Столбцов: {len(ads_data.columns)}")
        
        with col2:
            st.markdown("**CRM данные:**")
            st.write(f"- Клиентов всего: {len(crm_data)}")
            st.write(f"- Из рекламы: {len(crm_reklama)}")
            st.write(f"- Из других источников: {len(crm_drugoe)}")
    
    # Подвал
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <p>Создано с помощью ❤️ для анализа рекламной эффективности</p>
        <p>© 2024 Аналитика рекламы</p>
    </div>
    """, unsafe_allow_html=True)

# Инструкция для запуска
if not st.session_state.analysis_done:
    with st.expander("ℹ️ Как запустить приложение локально"):
        st.markdown("""
        ### Установка и запуск
        
        1. Установите Python 3.8 или выше
        2. Создайте папку для проекта
        3. В папке создайте два файла:
           - `requirements.txt` (с зависимостями)
           - `app.py` (основной код)
        4. Откройте терминал в папке проекта и выполните:
        
        ```bash
        pip install -r requirements.txt
        streamlit run app.py
        ```
        
        5. Откройте браузер по адресу: http://localhost:8501
        
        ### Развертывание на сервере
        
        Для размещения на сайте можно использовать:
        - Streamlit Cloud (бесплатно)
        - Heroku
        - AWS
        - DigitalOcean
        
        ### Streamlit Cloud (самый простой способ)
        
        1. Зарегистрируйтесь на https://streamlit.io/cloud
        2. Загрузите файлы в GitHub репозиторий
        3. Подключите репозиторий к Streamlit Cloud
        4. Приложение будет доступно по ссылке
        """)