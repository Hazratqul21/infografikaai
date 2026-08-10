/**
 * Skeleton — ma'lumot kelguncha ko'rsatiladigan "shakl".
 *
 * Nega kerak: hozir yuklanayotganda butunlay bo'sh ekran turardi va
 * foydalanuvchi ilova qotib qolgan deb o'ylardi. Skeleton nima kelishini
 * oldindan ko'rsatadi — kutish qisqaroq tuyuladi.
 */

export function Sk({ h = 16, w = "100%", r = 10, mb = 0 }: {
  h?: number; w?: number | string; r?: number; mb?: number;
}) {
  return <div className="sk" style={{ height: h, width: w, borderRadius: r, marginBottom: mb }} />;
}

/** Bosh sahifa skeleti — haqiqiy tartibni takrorlaydi */
export function HomeSkeleton() {
  return (
    <div className="screen">
      <div>
        <Sk h={24} w={110} r={100} mb={12} />
        <Sk h={26} w={190} mb={8} />
        <Sk h={14} w={240} />
      </div>
      <Sk h={215} r={28} />
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <Sk h={42} w={175} r={100} />
        <Sk h={42} w={120} r={100} />
        <Sk h={42} w={130} r={100} />
      </div>
      <div>
        <Sk h={18} w={120} mb={12} />
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Sk h={62} r={16} />
          <Sk h={62} r={16} />
          <Sk h={62} r={16} />
        </div>
      </div>
    </div>
  );
}

export function GallerySkeleton() {
  return (
    <div className="screen">
      <div>
        <Sk h={24} w={140} mb={8} />
        <Sk h={14} w={100} />
      </div>
      <div className="gal">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{ aspectRatio: "3/4" }}>
            <Sk h={0} w="100%" r={20} />
            <div className="sk" style={{ width: "100%", height: "100%", borderRadius: 20 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function WalletSkeleton() {
  return (
    <div className="screen">
      <div>
        <Sk h={24} w={120} mb={8} />
        <Sk h={14} w={200} />
      </div>
      <Sk h={175} r={28} />
      <Sk h={210} r={24} />
    </div>
  );
}
