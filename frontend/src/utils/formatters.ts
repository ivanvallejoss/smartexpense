export const formatDate = (isoString: string) => {
    const date = new Date(isoString);

    return new Intl.DateTimeFormat('es-AR', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Argentina/Buenos_Aires'
    }).format(date);
};