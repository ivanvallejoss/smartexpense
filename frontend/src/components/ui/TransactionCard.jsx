import { Calendar, Tag } from 'lucide-react';

const TransactionCard = ({ merchant, amount, category, date }) => {
  return (
    <div className="bg-white rounded-lg shadow-md p-4 max-w-sm border border-gray-100">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold text-gray-800">{merchant}</h3>
        <span className="text-lg font-bold text-gray-900">${amount}</span>
      </div>
      
      <div className="flex items-center gap-4 text-sm text-gray-600">
        <div className="flex items-center gap-1">
          <Tag className="w-4 h-4" />
          <span>{category}</span>
        </div>
        <div className="flex items-center gap-1">
          <Calendar className="w-4 h-4" />
          <span>{date}</span>
        </div>
      </div>
    </div>
  );
};

export default TransactionCard;
