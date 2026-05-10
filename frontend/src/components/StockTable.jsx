const SIGN = {
  '1': { label: '상한가', color: '#e74c3c' },
  '2': { label: '▲', color: '#e74c3c' },
  '3': { label: '-', color: '#888' },
  '4': { label: '하한가', color: '#3498db' },
  '5': { label: '▼', color: '#3498db' },
}

function StockTable({ stocks }) {
  if (stocks.length === 0) return <p className="status">스크리닝 결과가 없습니다.</p>

  return (
    <table>
      <thead>
        <tr>
          <th>종목코드</th>
          <th>종목명</th>
          <th>현재가</th>
          <th>등락</th>
          <th>등락률</th>
          <th>거래량</th>
        </tr>
      </thead>
      <tbody>
        {stocks.map(stock => {
          const sign = SIGN[stock.sign] ?? SIGN['3']
          return (
            <tr key={stock.shcode}>
              <td>{stock.shcode}</td>
              <td>{stock.hname}</td>
              <td>{stock.price.toLocaleString()}</td>
              <td style={{ color: sign.color }}>
                {sign.label} {Math.abs(stock.change).toLocaleString()}
              </td>
              <td style={{ color: sign.color }}>
                {stock.diff > 0 ? '+' : ''}{stock.diff}%
              </td>
              <td>{stock.volume.toLocaleString()}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default StockTable
