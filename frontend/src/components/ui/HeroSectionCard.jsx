const HeroSectionCard = () => {
    return (
        <div className="bg-surface-light dark:bg-surface-dark rounded-3xl p-6 shadow-soft relative overflow-hidden group">
            <div className="absolute -top-10 -right-10 w-40 h-40 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>
            <div className="relative z-10 flex flex-col gap-1 mb-6">
                <h2 className="text-text-muted dark:text-gray-400 text-sm font-medium uppercase tracking-wider">Weekly Spend</h2>
                <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold tracking-tight text-text-main dark:text-white">$342.50</span>
                </div>
                <p className="text-sm text-text-muted dark:text-gray-500 font-medium mt-1">of <span className="text-text-main dark:text-gray-300 font-bold">$500.00</span> budget</p>
            </div>
            <div className="relative z-10">
                <div className="flex justify-between text-xs font-semibold mb-2 text-primary">
                    <span>68% Used</span>
                    <span>$157.50 Left</span>
                </div>
                <div className="h-3 w-full bg-gray-100 dark:bg-neutral-700 rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full transition-all duration-1000 ease-out" style={{ width: '68%', boxShadow: '0 0 10px rgba(68, 196, 202, 0.4)' }}></div>
                </div>
            </div>
        </div>
    );
};

export default HeroSectionCard;