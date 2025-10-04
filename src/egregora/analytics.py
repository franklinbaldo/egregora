"""DataFrame-native analytics for conversation health and patterns.

This module provides powerful analytics capabilities leveraging pandas
for analyzing WhatsApp conversation patterns, user interactions, and
conversation health metrics.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, Any

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False


def get_conversation_health(df) -> Dict[str, Any]:
    """Calculate comprehensive conversation health metrics.
    
    Analyzes message distribution, participation patterns, and temporal
    characteristics to assess the health of a conversation.
    
    Args:
        df: pandas DataFrame with columns: timestamp, date, author, message
        
    Returns:
        Dictionary with health metrics
        
    Raises:
        ImportError: If pandas is not available
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return {}
    
    # Basic metrics
    total_messages = len(df)
    active_participants = df['author'].nunique()
    date_range = df['date'].max() - df['date'].min()
    
    # Participation distribution analysis
    messages_per_participant = df.groupby('author').size()
    participation_mean = messages_per_participant.mean()
    participation_std = messages_per_participant.std()
    
    # Calculate Gini coefficient for message distribution inequality
    gini_coefficient = calculate_gini(messages_per_participant)
    
    # Response time analysis
    df_sorted = df.sort_values('timestamp')
    response_times = df_sorted['timestamp'].diff().dt.total_seconds() / 60  # minutes
    median_response_time = response_times.median()
    
    # Thread detection
    df_with_threads = detect_threads(df)
    thread_count = df_with_threads['thread_id'].nunique() if 'thread_id' in df_with_threads.columns else 0
    
    # Daily activity patterns
    daily_activity = df.groupby('date').size()
    
    return {
        'total_messages': total_messages,
        'active_participants': active_participants,
        'messages_per_participant_avg': participation_mean,
        'messages_per_participant_std': participation_std,
        'gini_coefficient': gini_coefficient,  # 0 = perfect equality, 1 = maximum inequality
        'response_time_median_minutes': median_response_time,
        'thread_count': thread_count,
        'conversation_span_days': date_range.days if date_range else 0,
        'messages_per_day_avg': daily_activity.mean(),
        'most_active_day': daily_activity.idxmax(),
        'max_messages_in_day': daily_activity.max(),
        'activity_consistency': daily_activity.std() / daily_activity.mean() if daily_activity.mean() > 0 else 0,
    }


def calculate_gini(values) -> float:
    """Calculate Gini coefficient for measuring inequality.
    
    Args:
        values: pandas Series of values
        
    Returns:
        Gini coefficient (0 = perfect equality, 1 = maximum inequality)
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if len(values) == 0:
        return 0.0
    
    # Sort values
    sorted_values = values.sort_values()
    n = len(sorted_values)
    
    # Calculate Gini coefficient
    index = range(1, n + 1)
    gini = 2 * sum(index * sorted_values) / (n * sum(sorted_values)) - (n + 1) / n
    
    return gini


def get_influence_scores(df):
    """Calculate influence scores for participants.
    
    Influence is based on:
    - Message volume (30%)
    - Thread initiation (40%) 
    - Replies received (30%)
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        DataFrame with influence rankings
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.DataFrame()
    
    # Get interaction patterns
    interaction_matrix = get_interaction_matrix(df)
    thread_starters = get_thread_starters(df)
    
    # Calculate base metrics per author
    author_stats = df.groupby('author').agg(
        message_count=('message', 'count'),
        first_seen=('timestamp', 'min'),
        last_seen=('timestamp', 'max'),
    ).reset_index()
    
    # Add thread starter counts
    thread_counts = thread_starters.value_counts()
    author_stats['threads_started'] = author_stats['author'].map(thread_counts).fillna(0)
    
    # Add replies received
    if not interaction_matrix.empty:
        replies_received = interaction_matrix.groupby('replied_to')['interaction_count'].sum()
        author_stats['replies_received'] = author_stats['author'].map(replies_received).fillna(0)
    else:
        author_stats['replies_received'] = 0
    
    # Calculate normalized influence score
    max_messages = author_stats['message_count'].max() if len(author_stats) > 0 else 1
    max_threads = author_stats['threads_started'].max() if len(author_stats) > 0 else 1
    max_replies = author_stats['replies_received'].max() if len(author_stats) > 0 else 1
    
    author_stats['influence'] = (
        (author_stats['message_count'] / max_messages) * 0.3 +
        (author_stats['threads_started'] / max_threads) * 0.4 +
        (author_stats['replies_received'] / max_replies) * 0.3
    )
    
    return author_stats.sort_values('influence', ascending=False)


def get_interaction_matrix(df):
    """Build interaction matrix showing who responds to whom.
    
    Uses temporal proximity to infer reply relationships.
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        DataFrame with columns: author, replied_to, interaction_count
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.DataFrame(columns=['author', 'replied_to', 'interaction_count'])
    
    # Sort by timestamp
    df_sorted = df.sort_values('timestamp').copy()
    
    # Create 'replied_to' column based on previous message author
    df_sorted['replied_to'] = df_sorted['author'].shift(1)
    
    # Count interactions (exclude self-replies)
    interactions = df_sorted[df_sorted['author'] != df_sorted['replied_to']]
    
    if interactions.empty:
        return pd.DataFrame(columns=['author', 'replied_to', 'interaction_count'])
    
    interaction_counts = (
        interactions.groupby(['author', 'replied_to'])
        .size()
        .reset_index(name='interaction_count')
    )
    
    return interaction_counts.sort_values('interaction_count', ascending=False)


def detect_threads(df, max_gap_minutes: int = 30):
    """Detect conversation threads based on temporal gaps.
    
    Args:
        df: pandas DataFrame with conversation data
        max_gap_minutes: Maximum time gap between messages in same thread
        
    Returns:
        DataFrame with additional 'thread_id' column
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return df.copy()
    
    df_sorted = df.sort_values('timestamp').copy()
    
    # Calculate time gaps between messages
    df_sorted['gap_minutes'] = df_sorted['timestamp'].diff().dt.total_seconds() / 60
    
    # Mark new threads where gap exceeds threshold
    df_sorted['new_thread'] = (df_sorted['gap_minutes'] > max_gap_minutes) | df_sorted['gap_minutes'].isna()
    
    # Assign thread IDs
    df_sorted['thread_id'] = df_sorted['new_thread'].cumsum()
    
    return df_sorted


def get_thread_starters(df):
    """Identify who starts conversation threads.
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        pandas Series with thread starter authors
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    df_with_threads = detect_threads(df)
    
    if df_with_threads.empty:
        return pd.Series(dtype='object')
    
    # Get first message of each thread
    thread_starters = df_with_threads.groupby('thread_id')['author'].first()
    
    return thread_starters


def analyze_hourly_activity(df):
    """Analyze message distribution by hour of day.
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        pandas Series with message counts by hour (0-23)
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.Series(dtype='int64')
    
    return df.groupby(df['timestamp'].dt.hour).size()


def analyze_daily_activity(df):
    """Analyze message distribution by day.
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        pandas Series with message counts by date
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.Series(dtype='int64')
    
    return df.groupby('date').size()


def get_participation_timeline(df):
    """Get participation timeline showing when each author was active.
    
    Args:
        df: pandas DataFrame with conversation data
        
    Returns:
        DataFrame with author activity ranges
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.DataFrame()
    
    participation = df.groupby('author').agg(
        first_message=('timestamp', 'min'),
        last_message=('timestamp', 'max'),
        total_messages=('message', 'count'),
        active_days=('date', 'nunique'),
    ).reset_index()
    
    # Calculate activity span
    participation['activity_span_days'] = (
        participation['last_message'] - participation['first_message']
    ).dt.days
    
    # Calculate messages per day
    participation['messages_per_day'] = (
        participation['total_messages'] / participation['activity_span_days'].replace(0, 1)
    )
    
    return participation.sort_values('total_messages', ascending=False)


def detect_emerging_topics(df, recent_days: int = 7):
    """Detect topics that have grown in importance recently.
    
    Uses simple word frequency analysis to compare recent vs historical patterns.
    
    Args:
        df: pandas DataFrame with conversation data
        recent_days: Number of recent days to compare against historical
        
    Returns:
        DataFrame with emerging topic keywords
    """
    if not _PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analytics operations")
    
    if df.empty:
        return pd.DataFrame()
    
    # Split into recent and historical
    recent_threshold = df['date'].max() - timedelta(days=recent_days)
    recent_df = df[df['date'] > recent_threshold]
    historical_df = df[df['date'] <= recent_threshold]
    
    if recent_df.empty or historical_df.empty:
        return pd.DataFrame()
    
    # Simple word frequency analysis
    def get_word_frequencies(messages):
        words = []
        for message in messages:
            # Basic word extraction (can be enhanced with proper NLP)
            words.extend(message.lower().split())
        
        # Filter out common words (basic stopword removal)
        common_words = {'o', 'a', 'de', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já', 'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era', 'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'suas', 'nem', 'às', 'meu', 'minha', 'numa', 'pelos', 'pelas', 'essa', 'esse', 'este', 'esta', 'então', 'ainda', 'hoje', 'aqui', 'agora', 'sempre', 'todos', 'bem', 'pode', 'aí', 'onde', 'quem', 'tudo', 'vai', 'sim', 'sobre', 'vez', 'tanto', 'qual', 'cada', 'pouco', 'antes', 'menos', 'outro', 'outra', 'durante', 'alguns', 'algum', 'onde', 'dia', 'tempo', 'assim', 'lugar', 'ano', 'trabalho', 'casa', 'duas', 'dois', 'nome', 'lado', 'parte', 'grande', 'primeiro', 'primeira', 'última', 'último', 'pessoa', 'coisa', 'coisas', 'novo', 'nova', 'toda', 'todo', 'nada', 'vida', 'país', 'mão', 'mãos', 'nunca', 'vezes', 'alta', 'alto', 'baixo', 'baixa', 'nova', 'novo', 'dir', 'esq', 'direita', 'esquerda', 'faz', 'fazer', 'feito', 'feita', 'vou', 'vamos', 'vai', 'foram', 'são', 'sou', 'estar', 'estava', 'estão', 'estou', 'teve', 'tive', 'ter', 'tinha', 'temos', 'tenho', 'ter', 'fala', 'falar', 'falou', 'disse', 'dizer', 'ver', 'viu', 'visto', 'olha', 'olhar', 'quer', 'querer', 'saber', 'sei', 'sabia', 'sabe', 'pode', 'poder', 'poderia', 'deve', 'dever', 'deveria', 'gente', 'pessoal', 'aqui', 'aí', 'lá', 'ali'}
        
        words = [w for w in words if len(w) > 2 and w not in common_words]
        
        word_freq = pd.Series(words).value_counts()
        return word_freq
    
    recent_freq = get_word_frequencies(recent_df['message'])
    historical_freq = get_word_frequencies(historical_df['message'])
    
    # Calculate growth ratios
    emerging = []
    for word in recent_freq.index[:50]:  # Top 50 recent words
        recent_count = recent_freq[word]
        historical_count = historical_freq.get(word, 0)
        
        # Calculate growth ratio (with smoothing)
        growth_ratio = recent_count / (historical_count + 1)
        
        if growth_ratio > 2 and recent_count >= 3:  # Significant growth
            emerging.append({
                'word': word,
                'recent_count': recent_count,
                'historical_count': historical_count,
                'growth_ratio': growth_ratio
            })
    
    return pd.DataFrame(emerging).sort_values('growth_ratio', ascending=False)


__all__ = [
    'get_conversation_health',
    'calculate_gini',
    'get_influence_scores', 
    'get_interaction_matrix',
    'detect_threads',
    'get_thread_starters',
    'analyze_hourly_activity',
    'analyze_daily_activity',
    'get_participation_timeline',
    'detect_emerging_topics',
]