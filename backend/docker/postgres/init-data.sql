-- Kết nối vào database vừa tạo
\connect productdb

-- Tạo bảng danh mục
CREATE TABLE categories (
                            id INT PRIMARY KEY,
                            name TEXT NOT NULL
);

-- Tạo bảng sản phẩm
CREATE TABLE product (
                         product_id INT PRIMARY KEY,
                         product_name TEXT NOT NULL,
                         quantity INT NOT NULL,
                         price INT NOT NULL,
                         category_id INT REFERENCES categories(id),
                         image_link TEXT,
                         description TEXT
);

-- Chèn category mẫu
INSERT INTO categories (id, name) VALUES
                                      (1, 'Tai nghe'),
                                      (2, 'Đồng hồ'),
                                      (3, 'Điện thoại'),
                                      (4, 'Chuột máy tính')
    ON CONFLICT (id) DO NOTHING;

-- Chèn sản phẩm mẫu
INSERT INTO product (product_id, product_name, quantity, price, category_id, image_link, description)
VALUES
    (1, 'Tai nghe Bluetooth', 50, 199000, 1, 'https://down-vn.img.susercontent.com/file/sg-11134301-7repq-m8yxjaj41d3kd1.webp', 'Tai nghe không dây tiện lợi'),
    (2, 'Tai nghe không dây', 100, 250000, 1, 'https://down-vn.img.susercontent.com/file/sg-11134301-7ravi-madn8p060zmr3b.webp', 'Tai nghe chất lượng cao'),
    (3, 'Đồng hồ thông minh', 50, 10000, 2, 'https://down-vn.img.susercontent.com/file/sg-11134201-7rdw7-mc7rdu16aiz5d3.webp', 'Đồng hồ màn hình cảm ứng'),
    (4, 'Điện thoại Xiaomi', 60, 4100, 3, 'https://down-vn.img.susercontent.com/file/vn-11134207-7ras8-m4u6rv7qzum0e1.webp', 'Điện thoại thông minh nhiều chức năng'),
    (5, 'Chuột logitech', 70, 1690, 4, 'https://down-vn.img.susercontent.com/file/vn-11134207-7ras8-mcn7zibwp7zh40.webp', 'Chuột máy tính tiện lợi')
    ON CONFLICT (product_id) DO NOTHING;
