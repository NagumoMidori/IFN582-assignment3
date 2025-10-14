CREATE DATABASE assessment3;
USE assessment3;

CREATE TABLE admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
	username VARCHAR(100) UNIQUE NOT NULL,
	admin_password VARCHAR(255) NOT NULL
);

CREATE TABLE addresses (
address_id INT AUTO_INCREMENT PRIMARY KEY,
streetNumber VARCHAR(20) NOT NULL,
streetName VARCHAR(100) NOT NULL,
city VARCHAR(50) NOT NULL,
state VARCHAR(50) NOT NULL,
postcode VARCHAR(10) NOT NULL,
country VARCHAR(100) NOT NULL
);

CREATE TABLE categories (
category_id INT AUTO_INCREMENT PRIMARY KEY,
categoryName VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE customers (
customer_id INT AUTO_INCREMENT PRIMARY KEY,
email VARCHAR(100) UNIQUE NOT NULL,
phone VARCHAR(20) UNIQUE NOT NULL,
customer_password VARCHAR(255) NOT NULL,
firstName VARCHAR(100) NOT NULL,
lastName VARCHAR(100) NOT NULL,
address_id INT,
newsletterSubscription TINYINT(1) NOT NULL DEFAULT 0,
FOREIGN KEY (address_id) REFERENCES addresses(address_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE vendors (
vendor_id INT AUTO_INCREMENT PRIMARY KEY,
email VARCHAR(100) UNIQUE NOT NULL,
phone VARCHAR(20) UNIQUE NOT NULL,
vendor_password VARCHAR(255) NOT NULL,
firstName VARCHAR(100) NOT NULL,
lastName VARCHAR(100) NOT NULL,
address_id INT,
artisticName VARCHAR(100) NOT NULL,
bio TEXT NOT NULL,
profilePictureLink VARCHAR(255) NOT NULL,
FOREIGN KEY (address_id) REFERENCES addresses(address_id) ON DELETE SET NULL ON UPDATE CASCADE
);



CREATE TABLE artworks (
artwork_id INT AUTO_INCREMENT PRIMARY KEY,
vendor_id INT NOT NULL, 
category_id INT,
title VARCHAR(100) NOT NULL,
itemDescription TEXT NOT NULL,
pricePerWeek DECIMAL(10,2) NOT NULL,
imageLink VARCHAR(255) NOT NULL,
availabilityStartDate DATE,
availabilityEndDate DATE,
maxQuantity INT NOT NULL,
availabilityStatus ENUM('Listed', 'Leased', 'Unlisted') NOT NULL DEFAULT 'Unlisted',
FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id) ON DELETE RESTRICT ON UPDATE CASCADE
);




CREATE TABLE carts (
cart_id INT AUTO_INCREMENT PRIMARY KEY,
cartToken INT UNIQUE NOT NULL,
customer_id INT,
cart_status ENUM('Active', 'Abandoned', 'Converted') NOT NULL DEFAULT 'Active',
deliveryAddressID INT,
FOREIGN KEY (deliveryAddressID) REFERENCES addresses(address_id) ON DELETE SET NULL ON UPDATE CASCADE,
FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE cart_items (
cartItem_id INT AUTO_INCREMENT PRIMARY KEY, 
cart_id INT,
artwork_id INT,
quantity INT,
rentalDuration INT,
FOREIGN KEY (cart_id) REFERENCES carts(cart_id) ON DELETE CASCADE ON UPDATE CASCADE,
FOREIGN KEY (artwork_id) REFERENCES artworks(artwork_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE orders (
order_id INT AUTO_INCREMENT PRIMARY KEY,
customer_id INT,
orderStatus ENUM('Pending', 'Confirmed', 'Cancelled') DEFAULT 'Pending',
orderDate DATETIME,
billingAddressID INT,
deliveryAddressID INT,
FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT ON UPDATE CASCADE,
FOREIGN KEY (billingAddressID)  REFERENCES addresses(address_id)  ON DELETE SET NULL ON UPDATE CASCADE,
FOREIGN KEY (deliveryAddressID) REFERENCES addresses(address_id)  ON DELETE SET NULL ON UPDATE CASCADE 
);

CREATE TABLE order_item (
orderItem_id INT AUTO_INCREMENT PRIMARY KEY,
order_id INT,
artwork_id INT,
quantity INT DEFAULT 1,
rentalDuration INT,
unitPrice DECIMAL(10,2),
FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE  ON UPDATE CASCADE,
FOREIGN KEY (artwork_id) REFERENCES artworks(artwork_id) ON DELETE RESTRICT ON UPDATE CASCADE
);



INSERT INTO addresses (address_id, streetNumber, streetName, city, state, postcode, country) VALUES
(1,'101','Station St','Toowoomba','QLD','4350','Australia'),
(2,'22','Riverwalk Ave','West End','QLD','4101','Australia'),
(3,'5','Story Bridge Rd','Kangaroo Point','QLD','4169','Australia'),
(4,'77','Adelaide St','Brisbane','QLD','4000','Australia'),
(5,'30','Vulture St','South Brisbane','QLD','4101','Australia'),
(6,'12','Boundary St','West End','QLD','4101','Australia'),
(7, 128, 'Aerodrome Road', 'Maroochydore', 'QLD', 4558, 'Australia'),
(8, 42, 'Mooloolaba Esplanade', 'Mooloolaba', 'QLD', 4557, 'Australia'),
(9, 75, 'Main Street', 'Buderim', 'QLD', 4556, 'Australia'),
(10, 214, 'Bulcock Street', 'Caloundra', 'QLD', 4551, 'Australia'),
(11, 990, 'David Low Way', 'Coolum Beach', 'QLD', 4573, 'Australia'),
(12, 15, 'Lake Kawana Boulevard', 'Birtinya', 'QLD', 4575, 'Australia');

INSERT INTO categories (category_id, categoryName) VALUES
(1,'Painting'),
(2,'Drawing'),
(3,'Photography'),
(4,'Sculpture'),
(5,'Digital Art'),
(6,'Mixed Media');

INSERT INTO admins (admin_id, username, admin_password) VALUES
(1,'admin1','hash1'),
(2,'admin2','hash2');

INSERT INTO vendors (vendor_id, email, phone, vendor_password, firstName, lastName, address_id, artisticName, bio, profilePictureLink) VALUES
(1,'loremipsum@project582.com','0401000001','hashA','Lorem','Ipsum',6,'LorIp','Abstracts from Brisbane River.','averie-woodard-4nulm-JUYFo-unsplash.jpg'),
(2,'dolorsitamet@project582.com','0401000002','hashB','Dolor','Sit Amet',5,'DodoSA','Minimalist line drawings','charlie-green-3JmfENcL24M-unsplash.jpg'),
(3,'sedvitae@project582.com','0401000003','hashC','Sed','Vitae',4,'S-Vit','Limited prints.','raamin-ka-uR51HXLO7G0-unsplash.jpg'),
(4,'namiabortis@project582.com','0401000004','hashD','Nam','Iobortis',3,'NamIo','Original only.','vicky-hladynets-uyaTT9u6AvI-unsplash.jpg'),
(5,'utvulputate@project582.com','0401000005','hashE','Ut','Vulputate',2,'Utate','An intimate gallery.','tamara-bellis-JoKS3XweV50-unsplash.jpg'),
(6,'nullaeget@project582.com','0401000006','hashF','Nulla','Eget',1,'Mr. Eget','Abstracts from Toowoomba.','cord-allman-qMK2NZXIhP0-unsplash.jpg');

INSERT INTO customers (customer_id, email, phone, customer_password, firstName, lastName, address_id, newsletterSubscription) VALUES
(1,'dusty@example.com','0411000001','123456','Dusty','Lee',7,0),
(2,'erin@example.com','0412000002','112233445566','Erin','Silva',8,0),
(3,'alice@example.com','0413000003','password','Alice','Tran',9,1),
(4,'ben@example.com','0414000004','p@assword','Ben','Carter',10,1),
(5,'chloe@example.com','0415000005','pa$$word','Chloe','James',11,1);

INSERT INTO artworks (artwork_id, vendor_id, category_id, title, itemDescription, pricePerWeek, imageLink, availabilityStartDate, availabilityEndDate, maxQuantity, availabilityStatus)
VALUES
(1,1,1,'River Flow','Acrylic on canvas',30,'/img/a001.jpg','2025-03-01','2025-12-11',1,'Listed'),
(2,1,1,'Blue Currents','Mixed media',55,'/img/a002.jpg','2025-07-29','2025-08-30',1,'Listed'),
(3,1,1,'Evening Light','Oil on board',25,'/img/a003.jpg','2025-05-05','2025-12-31',1,'Listed'),
(4,1,1,'Harbour Mist','Acrylic on canvas',32,'/img/a004.jpg','2025-06-01','2025-12-31',1,'Listed'),
(5,1,1,'Seagrass','Oil on canvas',40,'/img/a005.jpg','2025-06-15','2025-12-31',1,'Listed'),
(6,1,1,'Sunrise Lane','Oil on board',28,'/img/a006.jpg','2025-06-20','2025-12-31',1,'Listed'),
(7,1,1,'Bush Track','Acrylic on canvas',22,'/img/a007.jpg','2025-07-01','2025-12-31',1,'Listed'),
(8,1,1,'Glasshouse','Oil on linen',48,'/img/a008.jpg','2025-07-05','2025-12-31',1,'Listed'),
(9,2,2,'Stone Arc','Carved sandstone',45,'/img/a009.jpg','2025-06-03','2025-12-31',1,'Listed'),
(10,2,2,'Copper Wave','Cold-forged copper',38,'/img/a010.jpg','2025-06-10','2025-12-31',1,'Listed'),
(11,2,2,'Timber Form','Reclaimed timber',26,'/img/a011.jpg','2025-06-25','2025-12-31',1,'Listed'),
(12,2,2,'Marble Fold','White marble',60,'/img/a012.jpg','2025-07-02','2025-12-31',1,'Listed'),
(13,1,4,'Story Bridge Dawn','High-res JPEG',15,'/img/a013.jpg','2025-05-05','2025-12-31',999,'Listed'),
(14,1,4,'Night City Print','A3 Giclée digital',11,'/img/a014.jpg','2025-06-11','2025-12-11',999,'Listed'),
(15,2,3,'Portrait Session 1hr','Studio portrait booking',120,'/img/a015.jpg','2025-07-15','2025-12-31',10,'Listed');

INSERT INTO orders (order_id, customer_id, orderStatus, orderDate, billingAddressID, deliveryAddressID)
VALUES (1, 1, 'Confirmed', '2025-08-10 10:00:00', 3, 3);

INSERT INTO order_item (orderItem_id, order_id, artwork_id, quantity, rentalDuration, unitPrice)
VALUES (1, 1, 15, 1, 1, 120.00);  

INSERT INTO orders (order_id, customer_id, orderStatus, orderDate, billingAddressID, deliveryAddressID)
VALUES (2, 2, 'Confirmed', '2025-08-12 09:15:00', 4, 5);

INSERT INTO order_item (orderItem_id, order_id, artwork_id, quantity, rentalDuration, unitPrice)
VALUES (2, 2, 2, 1, 4, 55.00);     

INSERT INTO orders (order_id, customer_id, orderStatus, orderDate, billingAddressID, deliveryAddressID)
VALUES (3, 1, 'Confirmed', '2025-08-15 14:30:00', 3, 3);

INSERT INTO order_item (orderItem_id, order_id, artwork_id, quantity, rentalDuration, unitPrice)
VALUES (3, 3, 13, 1, 1, 15.00);    -- purchase (treated as 1 period for consistency)

