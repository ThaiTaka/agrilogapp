import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";

import "./globals.css";

// Phông có đủ dấu tiếng Việt. Geist mặc định của create-next-app không phủ hết
// bộ dấu, nên "ệ" hay "ữ" sẽ rơi về phông dự phòng và chữ trông chắp vá.
const beVietnam = Be_Vietnam_Pro({
  variable: "--font-be-vietnam",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "AgriLog Admin",
    template: "%s · AgriLog Admin",
  },
  description: "Trang quản trị hệ thống nhật ký canh tác AgriLog",
  // Trang quản trị nội bộ, không có lý do gì để nằm trong kết quả tìm kiếm.
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" className={`${beVietnam.variable} h-full antialiased`}>
      <body className="min-h-full bg-slate-50 font-sans text-slate-900">
        {children}
      </body>
    </html>
  );
}
