import pandas as pd
df = pd.read_parquet("master_df.parquet")
print(df[["future_return_120d", "market_future_return_120d", "alpha_120d"]].describe())
