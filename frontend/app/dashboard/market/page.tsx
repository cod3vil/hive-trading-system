"use client";

import { useMarketPrices } from "@/hooks/use-api";

export default function MarketPage() {
  const { data: prices = [], isLoading, error } = useMarketPrices();

  if (isLoading) {
    return <div className="text-gray-400">Loading...</div>;
  }

  if (error) {
    return (
      <div className="text-red-400">
        Failed to load market data: {error.message}
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Market Scanner</h1>

      {prices.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No market data available. Make sure Market Scanner is running.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {prices.map((price) => (
            <div
              key={price.symbol}
              className="bg-gray-800 rounded-lg p-6 border border-gray-700"
            >
              <div className="text-sm text-gray-400 mb-2">{price.symbol}</div>
              <div className="text-3xl font-bold text-white mb-4">
                $
                {price.price.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <div className="flex justify-between text-sm">
                <div>
                  <div className="text-gray-400">Bid</div>
                  <div className="text-green-400">
                    ${price.bid?.toFixed(2) ?? "-"}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Ask</div>
                  <div className="text-red-400">
                    ${price.ask?.toFixed(2) ?? "-"}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Spread</div>
                  <div className="text-gray-300">
                    {price.bid != null && price.ask != null
                      ? `$${(price.ask - price.bid).toFixed(2)}`
                      : "-"}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
